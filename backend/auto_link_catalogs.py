"""Auto-link catalog PDFs to products based on filename analysis"""
from app.database import SessionLocal
from app.models import Document, ProductDocument, ProductDocumentType
from openai import OpenAI
from app.config import settings
import json

def auto_link_all_catalogs():
    db = SessionLocal()
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    
    # Get all documents with "catalog" or "catalogue" in filename
    catalogs = db.query(Document).filter(
        Document.original_filename.like('%atalog%')
    ).all()
    
    print(f"Found {len(catalogs)} catalog documents")
    
    for doc in catalogs:
        # Check if already linked
        existing_links = db.query(ProductDocument).filter(
            ProductDocument.document_id == doc.id
        ).count()
        
        if existing_links > 0:
            print(f"Skipping {doc.original_filename} - already linked")
            continue
        
        # Use AI to detect products from filename
        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{
                    "role": "system",
                    "content": "Extract product names from filename. Return JSON with products array in snake_case."
                }, {
                    "role": "user",
                    "content": f"""Filename: {doc.original_filename}
                    
Common products: cat_ladder, court_marking, glass_partition, wood_flooring, vinyl_flooring, cork_flooring, spc_flooring, lvt_flooring, staircase, canopy, sunshade, bike_rack, artificial_grass, led_lantern, aluminium_tower, gate, gas_spring, railing, sports_flooring, bamboo_flooring

Return: {{"products": ["product1", "product2"]}}"""
                }],
                response_format={"type": "json_object"},
                temperature=0,
                max_tokens=100
            )
            
            result = json.loads(response.choices[0].message.content)
            products = result.get('products', [])
            
            if products:
                for product_name in products:
                    product_doc = ProductDocument(
                        product_name=product_name,
                        document_type=ProductDocumentType.CATALOG,
                        document_id=doc.id,
                        display_order=0,
                        is_active=True
                    )
                    db.add(product_doc)
                    print(f"✓ Linked {doc.original_filename} to {product_name}")
                
                db.commit()
            else:
                print(f"✗ No products detected for {doc.original_filename}")
        
        except Exception as e:
            print(f"✗ Error processing {doc.original_filename}: {str(e)}")
    
    db.close()
    print("\nDone!")

if __name__ == "__main__":
    auto_link_all_catalogs()
