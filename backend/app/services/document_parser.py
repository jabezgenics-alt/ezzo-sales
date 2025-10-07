from typing import List, Dict, Any
import PyPDF2
import csv
import json
from pathlib import Path
from openai import OpenAI
from app.config import settings


class DocumentParser:
    """Parse documents and extract text"""
    
    def __init__(self):
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
    
    def parse_pdf(self, file_path: str) -> str:
        """Extract text from PDF with fallback for corrupted files"""
        text = ""
        
        # Try PyPDF2 first
        try:
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page_num, page in enumerate(pdf_reader.pages):
                    page_text = page.extract_text()
                    text += f"\n--- Page {page_num + 1} ---\n{page_text}"
            return text
        except Exception as e:
            print(f"PyPDF2 failed: {str(e)}. Trying pdfplumber...")
        
        # Fallback to pdfplumber for corrupted PDFs
        try:
            import pdfplumber
            with pdfplumber.open(file_path) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    page_text = page.extract_text() or ""
                    text += f"\n--- Page {page_num + 1} ---\n{page_text}"
            return text
        except Exception as e:
            print(f"pdfplumber also failed: {str(e)}")
        
        # Last resort: try to read as raw text
        try:
            with open(file_path, 'rb') as f:
                import codecs
                content = f.read()
                # Try to decode as latin-1 which accepts all byte values
                text = content.decode('latin-1', errors='ignore')
                # Filter to only printable characters
                text = ''.join(char for char in text if char.isprintable() or char in '\n\r\t')
                return f"⚠️ PDF may be corrupted. Extracted raw text:\n\n{text[:10000]}..."
        except Exception as e:
            raise Exception(f"Error parsing PDF: Could not read with any method. {str(e)}")
    
    def parse_csv(self, file_path: str) -> str:
        """Extract text from CSV"""
        text = ""
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                csv_reader = csv.DictReader(file)
                rows = list(csv_reader)
                
                # Convert to readable format
                for i, row in enumerate(rows):
                    text += f"\n--- Row {i + 1} ---\n"
                    for key, value in row.items():
                        text += f"{key}: {value}\n"
        except Exception as e:
            raise Exception(f"Error parsing CSV: {str(e)}")
        
        return text
    
    def parse_txt(self, file_path: str) -> str:
        """Extract text from TXT file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                return file.read()
        except Exception as e:
            raise Exception(f"Error parsing TXT: {str(e)}")
    
    def parse_document(self, file_path: str, file_type: str) -> str:
        """Parse document based on type"""
        if file_type.lower() == 'pdf':
            return self.parse_pdf(file_path)
        elif file_type.lower() == 'csv':
            return self.parse_csv(file_path)
        elif file_type.lower() in ['txt', 'text']:
            return self.parse_txt(file_path)
        else:
            raise ValueError(f"Unsupported file type: {file_type}")
    
    def chunk_text(self, text: str, chunk_size: int = 2000) -> List[str]:
        """Split text into chunks with overlap"""
        chunks = []
        overlap = 200
        
        # Split by paragraphs first
        paragraphs = text.split('\n\n')
        
        current_chunk = ""
        for para in paragraphs:
            if len(current_chunk) + len(para) < chunk_size:
                current_chunk += para + "\n\n"
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = para + "\n\n"
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def extract_structured_data(self, chunk: str) -> Dict[str, Any]:
        """Use GPT-5 to extract structured data from chunk
        
        For pricing tables with multiple items, this extracts the MOST RELEVANT item.
        Priority: parquet/flooring services, then most specific match.
        """
        try:
            response = self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": """You are an expert at extracting pricing and product information from text.

IMPORTANT: If the text contains a PRICING TABLE with MULTIPLE items, extract the MOST SPECIFIC pricing item.

Priority order when multiple items are present:
1. Parquet/flooring-related services (sanding, varnishing, installation)
2. Specific per-unit pricing (per sqft, per sqm, per meter)
3. The item with the most detailed description

For example, from a table with:
- Marble Polishing: $1.50 per sqft
- Sanding and Varnishing: $1/psf
- Vinyl Flooring: $4.80/sqft

Choose "Sanding and Varnishing: $1/psf" if it's parquet-related.

Extract the following information:
1. Item name/product
2. Base price (as a number)
3. Price unit (e.g., per m², per unit, per sq ft, per psf, per sqft)
4. Conditions (as a list of conditions)
5. Location (if mentioned)

Return ONLY a JSON object with these keys: item_name, base_price, price_unit, conditions (array), location.
If information is not available, use null. For base_price, extract only the numeric value."""
                    },
                    {
                        "role": "user",
                        "content": f"Extract pricing information from this text:\n\n{chunk}"
                    }
                ],
                temperature=0,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            
            # Clean up the result
            if result.get('base_price'):
                try:
                    result['base_price'] = float(result['base_price'])
                except (ValueError, TypeError):
                    result['base_price'] = None
            
            return result
            
        except Exception as e:
            print(f"Error extracting structured data: {str(e)}")
            return {
                'item_name': None,
                'base_price': None,
                'price_unit': None,
                'conditions': [],
                'location': None
            }
    
    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings using OpenAI"""
        try:
            response = self.client.embeddings.create(
                model="text-embedding-3-small",
                input=texts
            )
            return [item.embedding for item in response.data]
        except Exception as e:
            print(f"Error generating embeddings: {str(e)}")
            return None
    
    def generate_summary(self, text: str, max_length: int = 500) -> str:
        """Generate a summary of the document using AI"""
        try:
            # Truncate text to avoid token limits
            # gpt-4o-mini has 8192 token context limit
            # ~4 chars per token, leaving room for system prompt + response
            max_chars = 6000  # Roughly 1500 tokens, leaves plenty of room for system prompt + response
            truncated_text = text[:max_chars] if len(text) > max_chars else text
            
            response = self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": f"""You are an expert at summarizing technical and pricing documents.
Create a concise summary (max {max_length} words) that highlights:
1. Main products/services covered
2. Key pricing information
3. Important terms and conditions
4. Any geographical or temporal limitations

Be specific and factual. Focus on information relevant for sales and pricing."""
                    },
                    {
                        "role": "user",
                        "content": f"Summarize this document:\n\n{truncated_text}"
                    }
                ],
                temperature=0.3,
                max_tokens=1000
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            print(f"Error generating summary: {str(e)}")
            # Return a generic message instead of the error details
            return "Unable to generate summary - document may be too large or complex."
    
    def generate_structured_knowledge_summary(self, document_summaries: List[Dict[str, str]]) -> str:
        """Generate a comprehensive structured summary of ALL documents in the knowledge base"""
        try:
            # Prepare document summaries text
            docs_text = ""
            for i, doc in enumerate(document_summaries, 1):
                docs_text += f"\n\n## Document {i}: {doc['filename']}\n{doc['summary']}"
            
            # Limit total length to avoid token limits
            max_chars = 6000
            if len(docs_text) > max_chars:
                docs_text = docs_text[:max_chars] + "\n\n[... additional documents truncated ...]"
            
            response = self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": """You are an expert at creating comprehensive, structured knowledge base summaries.

Create a well-organized summary of the entire knowledge base with the following structure:

# KNOWLEDGE BASE SUMMARY

## 1. PRODUCTS & SERVICES
List all products and services covered across all documents, categorized logically.

## 2. PRICING STRUCTURE
Summarize the pricing information, including:
- Base prices for key items
- Pricing units (per m², per unit, etc.)
- Price ranges and factors affecting pricing

## 3. TERMS & CONDITIONS
Key terms, conditions, and requirements mentioned across documents.

## 4. GEOGRAPHICAL COVERAGE
Locations, regions, or areas covered.

## 5. KEY INSIGHTS
Important notes, limitations, or special considerations.

Use markdown formatting. Be comprehensive but concise. Focus on actionable information for sales teams."""
                    },
                    {
                        "role": "user",
                        "content": f"Create a structured summary of this knowledge base based on these documents:{docs_text}"
                    }
                ],
                temperature=0.3,
                max_tokens=2000
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            print(f"Error generating knowledge base summary: {str(e)}")
            return "Unable to generate knowledge base summary."


# Singleton instance
document_parser = DocumentParser()
