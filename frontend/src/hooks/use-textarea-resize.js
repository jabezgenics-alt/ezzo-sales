import { useLayoutEffect, useRef } from "react";

export function useTextareaResize(value, rows = 1) {
  const textareaRef = useRef(null);

  useLayoutEffect(() => {
    const textArea = textareaRef.current;

    if (textArea) {
      // Get the line height to calculate minimum height based on rows
      const computedStyle = window.getComputedStyle(textArea);
      const lineHeight = parseInt(computedStyle.lineHeight, 10) || 20;
      const padding =
        parseInt(computedStyle.paddingTop, 10) +
        parseInt(computedStyle.paddingBottom, 10);

      // Calculate minimum height based on rows
      const minHeight = lineHeight * rows + padding;

      // Reset height to auto first to get the correct scrollHeight
      textArea.style.height = "0px";
      const scrollHeight = Math.max(textArea.scrollHeight, minHeight);

      // Set the final height
      textArea.style.height = `${scrollHeight + 2}px`;
    }
  }, [value, rows]);

  return textareaRef;
}

