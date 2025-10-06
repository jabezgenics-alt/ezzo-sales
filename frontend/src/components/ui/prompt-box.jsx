import * as React from "react";
import { Plus, Settings2, Send, X, Mic, Globe, Pencil, Lightbulb } from "lucide-react";
import { Tooltip, TooltipTrigger, TooltipContent, TooltipProvider } from "@/components/ui/tooltip";
import { Popover, PopoverTrigger, PopoverContent } from "@/components/ui/popover";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { cn } from "@/lib/utils";

// SVG Icon Components
const PaintBrushIcon = (props) => (
  <svg viewBox="0 0 512 512" fill="currentColor" className="w-4 h-4" {...props}>
    <g>
      <path d="M141.176,324.641l25.323,17.833c7.788,5.492,17.501,7.537,26.85,5.67c9.35-1.877,17.518-7.514,22.597-15.569l22.985-36.556l-78.377-55.222l-26.681,33.96c-5.887,7.489-8.443,17.081-7.076,26.511C128.188,310.69,133.388,319.158,141.176,324.641z"/>
      <path d="M384.289,64.9c9.527-15.14,5.524-35.06-9.083-45.355l-0.194-0.129c-14.615-10.296-34.728-7.344-45.776,6.705L170.041,228.722l77.067,54.292L384.289,64.9z"/>
    </g>
  </svg>
);

const TelescopeIcon = (props) => (
  <svg viewBox="0 0 512 512" fill="currentColor" className="w-4 h-4" {...props}>
    <g>
      <path d="M452.425,202.575l-38.269-23.11c-1.266-10.321-5.924-18.596-13.711-21.947l-86.843-52.444l-0.275,0.598c-3.571-7.653-9.014-13.553-16.212-16.668L166.929,10.412l-0.236,0.543v-0.016c-3.453-2.856-7.347-5.239-11.594-7.08C82.569-10.435,40.76,14.5,21.516,59.203C2.275,103.827,12.82,151.417,45.142,165.36c4.256,1.826,8.669,3.005,13.106,3.556l-0.19,0.464l146.548,40.669c7.19,3.107,15.206,3.004,23.229,0.37l-0.236,0.566L365.55,238.5c7.819,3.366,17.094,1.125,25.502-5.082l42.957,11.909c7.67,3.312,18.014-3.548,23.104-15.362C462.202,218.158,460.11,205.894,452.425,202.575z"/>
    </g>
  </svg>
);

const toolsList = [
  { id: 'createImage', name: 'Create an image', shortName: 'Image', icon: PaintBrushIcon },
  { id: 'searchWeb', name: 'Search the web', shortName: 'Search', icon: Globe },
  { id: 'writeCode', name: 'Write or code', shortName: 'Write', icon: Pencil },
  { id: 'deepResearch', name: 'Run deep research', shortName: 'Deep Search', icon: TelescopeIcon, extra: '5 left' },
  { id: 'thinkLonger', name: 'Think for longer', shortName: 'Think', icon: Lightbulb },
];

export const PromptBox = React.forwardRef(({ className, onSubmit, ...props }, ref) => {
  const internalTextareaRef = React.useRef(null);
  const fileInputRef = React.useRef(null);
  const [value, setValue] = React.useState("");
  const [imagePreview, setImagePreview] = React.useState(null);
  const [selectedTool, setSelectedTool] = React.useState(null);
  const [isPopoverOpen, setIsPopoverOpen] = React.useState(false);
  const [isImageDialogOpen, setIsImageDialogOpen] = React.useState(false);

  React.useImperativeHandle(ref, () => internalTextareaRef.current, []);

  React.useLayoutEffect(() => {
    const textarea = internalTextareaRef.current;
    if (textarea) {
      textarea.style.height = "auto";
      const newHeight = Math.min(textarea.scrollHeight, 200);
      textarea.style.height = `${newHeight}px`;
    }
  }, [value]);

  const handleInputChange = (e) => {
    setValue(e.target.value);
    if (props.onChange) props.onChange(e);
  };

  const handlePlusClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = (event) => {
    const file = event.target.files?.[0];
    if (file && file.type.startsWith("image/")) {
      const reader = new FileReader();
      reader.onloadend = () => {
        setImagePreview(reader.result);
      };
      reader.readAsDataURL(file);
    }
    event.target.value = "";
  };

  const handleRemoveImage = (e) => {
    e.stopPropagation();
    setImagePreview(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (onSubmit && (value.trim() || imagePreview)) {
      onSubmit({ message: value, image: imagePreview, tool: selectedTool });
      setValue("");
      setImagePreview(null);
      setSelectedTool(null);
    }
  };

  const hasValue = value.trim().length > 0 || imagePreview;
  const activeTool = selectedTool ? toolsList.find(t => t.id === selectedTool) : null;
  const ActiveToolIcon = activeTool?.icon;

  return (
    <form onSubmit={handleSubmit}>
      <div className={cn("flex flex-col rounded-[28px] p-2 shadow-sm transition-colors bg-white border border-gray-200 cursor-text", className)}>
        <input type="file" ref={fileInputRef} onChange={handleFileChange} className="hidden" accept="image/*" />

        {imagePreview && (
          <Dialog open={isImageDialogOpen} onOpenChange={setIsImageDialogOpen}>
            <div className="relative mb-1 w-fit rounded-[1rem] px-1 pt-1">
              <button type="button" className="transition-transform" onClick={() => setIsImageDialogOpen(true)}>
                <img src={imagePreview} alt="Image preview" className="h-14.5 w-14.5 rounded-[1rem]" />
              </button>
              <button onClick={handleRemoveImage} className="absolute right-2 top-2 z-10 flex h-4 w-4 items-center justify-center rounded-full bg-white/50 dark:bg-[#303030] text-black dark:text-white transition-colors hover:bg-accent dark:hover:bg-[#515151]" aria-label="Remove image">
                <X className="h-4 w-4" />
              </button>
            </div>
            <DialogContent>
              <img src={imagePreview} alt="Full size preview" className="w-full max-h-[95vh] object-contain rounded-[24px]" />
            </DialogContent>
          </Dialog>
        )}

        <textarea ref={internalTextareaRef} rows={1} value={value} onChange={handleInputChange} placeholder="Message..." className="custom-scrollbar w-full resize-none border-0 bg-transparent p-3 text-gray-900 placeholder:text-gray-400 focus:ring-0 focus-visible:outline-none min-h-12" {...props} />

        <div className="mt-0.5 p-1 pt-0">
          <TooltipProvider delayDuration={100}>
            <div className="flex items-center gap-2">
              <Tooltip>
                <TooltipTrigger asChild>
                  <button type="button" onClick={handlePlusClick} className="flex h-8 w-8 items-center justify-center rounded-full text-foreground dark:text-white transition-colors hover:bg-accent dark:hover:bg-[#515151] focus-visible:outline-none">
                    <Plus className="h-6 w-6" />
                    <span className="sr-only">Attach image</span>
                  </button>
                </TooltipTrigger>
                <TooltipContent side="top" showArrow={true}><p>Attach image</p></TooltipContent>
              </Tooltip>

              <Popover open={isPopoverOpen} onOpenChange={setIsPopoverOpen}>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <PopoverTrigger asChild>
                      <button type="button" className="flex h-8 items-center gap-2 rounded-full p-2 text-sm text-gray-700 transition-colors hover:bg-gray-100 focus-visible:outline-none">
                        <Settings2 className="h-4 w-4" />
                        {!selectedTool && 'Tools'}
                      </button>
                    </PopoverTrigger>
                  </TooltipTrigger>
                  <TooltipContent side="top" showArrow={true}><p>Explore Tools</p></TooltipContent>
                </Tooltip>
                <PopoverContent side="top" align="start">
                  <div className="flex flex-col gap-1">
                    {toolsList.map(tool => (
                      <button key={tool.id} type="button" onClick={() => { setSelectedTool(tool.id); setIsPopoverOpen(false); }} className="flex w-full items-center gap-2 rounded-md p-2 text-left text-sm hover:bg-accent dark:hover:bg-[#515151]">
                        <tool.icon className="h-4 w-4" />
                        <span>{tool.name}</span>
                        {tool.extra && <span className="ml-auto text-xs text-muted-foreground dark:text-gray-400">{tool.extra}</span>}
                      </button>
                    ))}
                  </div>
                </PopoverContent>
              </Popover>

              {activeTool && (
                <>
                  <div className="h-4 w-px bg-border dark:bg-gray-600" />
                  <button type="button" onClick={() => setSelectedTool(null)} className="flex h-8 items-center gap-2 rounded-full px-2 text-sm hover:bg-gray-100 cursor-pointer text-blue-600 transition-colors flex-row items-center justify-center">
                    {ActiveToolIcon && <ActiveToolIcon className="h-4 w-4" />}
                    {activeTool.shortName}
                    <X className="h-4 w-4" />
                  </button>
                </>
              )}

              <div className="ml-auto flex items-center gap-2">
                <Tooltip>
                  <TooltipTrigger asChild>
                    <button type="button" className="flex h-8 w-8 items-center justify-center rounded-full text-gray-700 transition-colors hover:bg-gray-100 focus-visible:outline-none">
                      <Mic className="h-5 w-5" />
                      <span className="sr-only">Record voice</span>
                    </button>
                  </TooltipTrigger>
                  <TooltipContent side="top" showArrow={true}><p>Record voice</p></TooltipContent>
                </Tooltip>

                <Tooltip>
                  <TooltipTrigger asChild>
                    <button type="submit" disabled={!hasValue} className="flex h-8 w-8 items-center justify-center rounded-full text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none bg-black text-white hover:bg-black/80 disabled:bg-gray-300">
                      <Send className="h-6 w-6 text-bold" />
                      <span className="sr-only">Send message</span>
                    </button>
                  </TooltipTrigger>
                  <TooltipContent side="top" showArrow={true}><p>Send</p></TooltipContent>
                </Tooltip>
              </div>
            </div>
          </TooltipProvider>
        </div>
      </div>
    </form>
  );
});

PromptBox.displayName = "PromptBox";
