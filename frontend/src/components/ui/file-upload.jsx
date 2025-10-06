import { useState, useRef, forwardRef, useImperativeHandle } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";
import {
  UploadCloud,
  File as FileIcon,
  Trash2,
  Loader,
  CheckCircle,
} from "lucide-react";

const FileUpload = forwardRef(({ onFilesUploaded }, ref) => {
  const [files, setFiles] = useState([]);
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const [isDragging, setIsDragging] = useState(false);
  const inputRef = useRef(null);

  // Expose clearFiles method to parent via ref
  useImperativeHandle(ref, () => ({
    clearFiles: () => {
      setFiles([]);
      setUploadedFiles([]);
    },
  }));

  // Process dropped or selected files
  const handleFiles = (fileList) => {
    const timestamp = Date.now();
    const newFiles = Array.from(fileList).map((file, index) => {
      const preview = URL.createObjectURL(file);
      // Use a unique ID that doesn't depend on the preview URL
      const uniqueId = `file-${timestamp}-${index}-${Math.random().toString(36).substr(2, 9)}`;
      return {
        id: uniqueId,
        preview,
        progress: 0,
        name: file.name,
        size: file.size,
        type: file.type,
        lastModified: file.lastModified,
        file,
      };
    });
    setFiles((prev) => [...prev, ...newFiles]);
    newFiles.forEach((f) => simulateUpload(f.id));
  };

  // Simulate upload progress
  const simulateUpload = (id) => {
    let progress = 0;
    const interval = setInterval(() => {
      progress += Math.random() * 15;
      setFiles((prev) =>
        prev.map((f) =>
          f.id === id ? { ...f, progress: Math.min(progress, 100) } : f,
        ),
      );
      if (progress >= 100) {
        clearInterval(interval);
        if (navigator.vibrate) navigator.vibrate(100);
      }
    }, 300);
  };

  // Handle upload button click - trigger actual upload
  const handleUploadClick = () => {
    const readyFiles = files.filter(f => f.progress === 100);
    if (readyFiles.length > 0 && onFilesUploaded) {
      onFilesUploaded(readyFiles);
    }
  };

  const onDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    handleFiles(e.dataTransfer.files);
  };

  const onDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const onDragLeave = () => setIsDragging(false);

  const onSelect = (e) => {
    if (e.target.files) handleFiles(e.target.files);
  };

  const formatFileSize = (bytes) => {
    if (!bytes) return "0 Bytes";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${(bytes / Math.pow(k, i)).toFixed(2)} ${sizes[i]}`;
  };

  const removeUploadedFile = (id) => {
    setUploadedFiles((prev) => prev.filter((f) => f.id !== id));
    // Don't call onFilesUploaded when removing files from display
  };

  return (
    <div className="w-full max-w-3xl mx-auto p-4 md:p-6">
      {/* Drop zone */}
      <motion.div
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
        initial={false}
        animate={{
          borderColor: isDragging ? "#3b82f6" : "#e5e5e5",
          scale: isDragging ? 1.02 : 1,
        }}
        whileHover={{ scale: 1.01 }}
        transition={{ duration: 0.2 }}
        className={cn(
          "relative rounded-2xl p-8 md:p-12 text-center cursor-pointer bg-neutral-50 border-2 border-dashed shadow-sm hover:shadow-md backdrop-blur group",
          isDragging && "ring-4 ring-blue-400/30 border-blue-500",
        )}
      >
        <div className="flex flex-col items-center gap-5">
          <motion.div
            animate={{ y: isDragging ? [-5, 0, -5] : 0 }}
            transition={{
              duration: 1.5,
              repeat: isDragging ? Infinity : 0,
              ease: "easeInOut",
            }}
            className="relative"
          >
            <motion.div
              animate={{
                opacity: isDragging ? [0.5, 1, 0.5] : 1,
                scale: isDragging ? [0.95, 1.05, 0.95] : 1,
              }}
              transition={{
                duration: 2,
                repeat: isDragging ? Infinity : 0,
                ease: "easeInOut",
              }}
              className="absolute -inset-4 bg-blue-400/10 rounded-full blur-md"
              style={{ display: isDragging ? "block" : "none" }}
            />
            <UploadCloud
              className={cn(
                "w-16 h-16 md:w-20 md:h-20 drop-shadow-sm transition-colors duration-300",
                isDragging
                  ? "text-blue-500"
                  : "text-neutral-700 group-hover:text-blue-500",
              )}
            />
          </motion.div>

          <div className="space-y-2">
            <h3 className="text-xl md:text-2xl font-semibold text-neutral-800">
              {isDragging
                ? "Drop files here"
                : files.length
                  ? "Add more files"
                  : "Upload your files"}
            </h3>
            <p className="text-neutral-600 md:text-lg max-w-md mx-auto">
              {isDragging ? (
                <span className="font-medium text-blue-500">
                  Release to upload
                </span>
              ) : (
                <>
                  Drag & drop files here, or{" "}
                  <span className="text-blue-500 font-medium">browse</span>
                </>
              )}
            </p>
            <p className="text-sm text-neutral-500">
              Supports images, documents, videos, and more
            </p>
          </div>

          <input
            ref={inputRef}
            type="file"
            multiple
            hidden
            onChange={onSelect}
            accept="image/*,application/pdf,video/*,audio/*,text/*,application/zip"
          />
        </div>
      </motion.div>

      {/* Files list */}
      <div className="mt-8">
        <AnimatePresence>
          {files.length > 0 && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex justify-between items-center mb-3 px-2"
            >
              <h3 className="font-semibold text-lg md:text-xl text-neutral-800">
                Files ready ({files.filter(f => f.progress === 100).length}/{files.length})
              </h3>
              <div className="flex gap-2">
                {files.filter(f => f.progress === 100).length > 0 && (
                  <button
                    onClick={handleUploadClick}
                    className="text-sm font-medium px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-md text-white transition-colors duration-200"
                  >
                    Upload {files.filter(f => f.progress === 100).length} files
                  </button>
                )}
                {files.length > 1 && (
                  <button
                    onClick={() => setFiles([])}
                    className="text-sm font-medium px-3 py-1 bg-neutral-100 hover:bg-neutral-200 rounded-md text-neutral-700 hover:text-red-600 transition-colors duration-200"
                  >
                    Clear all
                  </button>
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        <div
          className={cn(
            "flex flex-col gap-3 overflow-y-auto pr-2",
            files.length > 3 &&
              "max-h-96 custom-scrollbar",
          )}
        >
          <AnimatePresence>
            {files.map((file) => (
              <motion.div
                key={file.id}
                initial={{ opacity: 0, y: 20, scale: 0.97 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: -20, scale: 0.95 }}
                transition={{ type: "spring", stiffness: 300, damping: 24 }}
                className="px-4 py-4 flex items-start gap-4 rounded-xl bg-neutral-50 shadow hover:shadow-md transition-all duration-200"
              >
                {/* Thumbnail */}
                <div className="relative flex-shrink-0">
                  {file.type.startsWith("image/") ? (
                    <img
                      src={file.preview}
                      alt={file.name}
                      className="w-16 h-16 md:w-20 md:h-20 rounded-lg object-cover border border-neutral-200 shadow-sm"
                    />
                  ) : file.type.startsWith("video/") ? (
                    <video
                      src={file.preview}
                      className="w-16 h-16 md:w-20 md:h-20 rounded-lg object-cover border border-neutral-200 shadow-sm"
                      controls={false}
                      muted
                      loop
                      playsInline
                      preload="metadata"
                    />
                  ) : (
                    <FileIcon className="w-16 h-16 md:w-20 md:h-20 text-neutral-400" />
                  )}
                  {file.progress === 100 && (
                    <motion.div
                      initial={{ opacity: 0, scale: 0.5 }}
                      animate={{ opacity: 1, scale: 1 }}
                      className="absolute -right-2 -bottom-2 bg-white rounded-full shadow-sm"
                    >
                      <CheckCircle className="w-5 h-5 text-emerald-500" />
                    </motion.div>
                  )}
                </div>

                {/* File info & progress */}
                <div className="flex-1 min-w-0">
                  <div className="flex flex-col gap-1 w-full">
                    {/* Filename */}
                    <div className="flex items-center gap-2 min-w-0">
                      <FileIcon className="w-5 h-5 flex-shrink-0 text-blue-500" />
                      <h4
                        className="font-medium text-base md:text-lg truncate text-neutral-800"
                        title={file.name}
                      >
                        {file.name}
                      </h4>
                    </div>

                    {/* Details & remove/loading */}
                    <div className="flex items-center justify-between gap-3 text-sm text-neutral-500">
                      <span className="text-xs md:text-sm">
                        {formatFileSize(file.size)}
                      </span>
                      <span className="flex items-center gap-1.5">
                        <span className="font-medium">
                          {Math.round(file.progress)}%
                        </span>
                        {file.progress < 100 ? (
                          <Loader className="w-4 h-4 animate-spin text-blue-500" />
                        ) : (
                          <Trash2
                            className="w-4 h-4 cursor-pointer text-neutral-400 hover:text-red-500 transition-colors duration-200"
                            onClick={(e) => {
                              e.stopPropagation();
                              setFiles((prev) =>
                                prev.filter((f) => f.id !== file.id),
                              );
                            }}
                            aria-label="Remove file"
                          />
                        )}
                      </span>
                    </div>
                  </div>

                  {/* Progress bar */}
                  <div className="w-full h-2 bg-neutral-200 rounded-full overflow-hidden mt-3">
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: `${file.progress}%` }}
                      transition={{
                        duration: 0.4,
                        type: "spring",
                        stiffness: 100,
                        ease: "easeOut",
                      }}
                      className={cn(
                        "h-full rounded-full shadow-inner",
                        file.progress < 100 ? "bg-blue-500" : "bg-emerald-500",
                      )}
                    />
                  </div>
                </div>
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
});

FileUpload.displayName = 'FileUpload';

export default FileUpload;

