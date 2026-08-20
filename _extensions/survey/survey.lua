-- Render course surveys directly from the events metadata in course.yml.

local qr_counter = 0

local function value(value)
  if value == nil then
    return ""
  end
  return pandoc.utils.stringify(value)
end

local function session_key(session_id)
  local number = session_id:match("^session[-_](%d+)")
  if number == nil then
    return nil
  end
  return "session_" .. number, tonumber(number)
end

local function survey_url(meta, requested_session)
  local requested_key = session_key(requested_session)
  if requested_key == nil then
    return nil
  end

  local found = nil
  for _, event in ipairs(meta.events or {}) do
    local event_key = session_key(value(event.session_id))
    if event_key == requested_key then
      for _, material in ipairs(event.materials or {}) do
        local url = value(material.survey_url):match("^%s*(.-)%s*$")
        if url ~= "" and url:upper() ~= "TODO" then
          if found ~= nil and found ~= url then
            quarto.log.warning("Conflicting survey URLs configured for " .. requested_key)
            return nil
          end
          found = url
        end
      end
    end
  end
  return found
end

local function no_survey()
  -- This matches the old generated fragment: TODO and missing URLs are invisible.
  return pandoc.RawBlock("html", "<!-- No survey URL configured. -->")
end

local function qr_code(url)
  if quarto.doc.is_format("html:js") then
    quarto.doc.add_html_dependency {
      name = "qrcodejs",
      version = "v1.0.0",
      scripts = { "../jmbuhr/qrcode/assets/qrcode.js" },
    }
    qr_counter = qr_counter + 1
    local id = "survey-qrcode-" .. qr_counter
    local options = quarto.json.encode {
      text = url,
      width = 400,
      height = 400,
      colorDark = "#000000",
      colorLight = "#ffffff",
    }
    return pandoc.RawBlock("html", string.format([[
<div id="%s" class="qrcode"></div>
<script type="text/javascript">
(function() {
  var script = document.currentScript;
  var qrcode = script.previousElementSibling;
  qrcode.qrcode = new QRCode(qrcode, %s);
  script.remove();
})();
</script>]], id, options))
  elseif quarto.doc.is_format("pdf") then
    quarto.doc.use_latex_package("qrcode")
    return pandoc.RawBlock("latex", "\\qrcode[height=400px]{\\detokenize{" .. url .. "}}")
  end
  return pandoc.Null()
end

local function link(url, new_window)
  local attributes = {}
  if new_window then
    attributes.target = "_blank"
  end
  return pandoc.Link(url, url, "", attributes)
end

local function slide(number, url)
  return pandoc.Blocks {
    pandoc.Header(2, "Survey: Session " .. number, { ["data-state"] = "hide-menubar" }),
    pandoc.RawBlock("html", "<br><br>"),
    pandoc.Div(qr_code(url), { style = "display:flex; justify-content:center;" }),
    pandoc.RawBlock("html", "<br><br>"),
    pandoc.Plain(link(url, false)),
    pandoc.Div({
      pandoc.Para("Note: Responses may be analyzed and published in anonymized form."),
      pandoc.Para("Please complete the survey before you leave today — thank you 🙏"),
    }, { class = "aside" }),
  }
end

local function exercise(number, url)
  return pandoc.Para {
    pandoc.Str("Before you wrap up, please complete the Session " .. number .. " survey here: "),
    link(url, true),
    pandoc.Str(". Thank you 🙏"),
  }
end

return {
  survey = function(args, _, meta)
    local session = value(args[1])
    local variant = value(args[2]):lower()
    local _, number = session_key(session)
    if number == nil then
      quarto.log.warning("Survey shortcode requires a session such as session_01")
      return no_survey()
    end
    if variant ~= "slide" and variant ~= "exercise" then
      quarto.log.warning("Survey shortcode variant must be 'slide' or 'exercise'")
      return no_survey()
    end

    local url = survey_url(meta, session)
    if url == nil then
      return no_survey()
    end
    if variant == "slide" then
      return slide(number, url)
    end
    return exercise(number, url)
  end,
}
