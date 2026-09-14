local function argument(value)
  if value == nil then
    return "5"
  end

  local lines = pandoc.utils.stringify(value):match("^%s*(.-)%s*$")
  if not lines:match("^%d+%.?%d*$") or tonumber(lines) <= 0 then
    error("needspace shortcode requires one positive numeric argument")
  end
  return lines
end

return {
  needspace = function(args)
    if #args > 1 then
      error("needspace shortcode accepts at most one argument")
    end

    local lines = argument(args[1])
    if quarto.doc.is_format("latex") then
      quarto.doc.use_latex_package("needspace")
      return pandoc.RawBlock("latex", "\\Needspace{" .. lines .. "\\baselineskip}")
    end
    return pandoc.Null()
  end,
}
