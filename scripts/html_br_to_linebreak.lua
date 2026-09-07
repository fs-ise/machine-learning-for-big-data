-- Preserve HTML line breaks used inside Markdown table cells in PDF output.
function RawInline(element)
  if element.format == "html" and element.text:match("^<br%s*/?>$") then
    return pandoc.LineBreak()
  end
end
