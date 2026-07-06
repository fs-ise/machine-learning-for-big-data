-- Keep SVG image references as external files so reveal.js can load them normally.
function Image(img)
  if img.src:match('%.svg$') then
    return img
  end
end
