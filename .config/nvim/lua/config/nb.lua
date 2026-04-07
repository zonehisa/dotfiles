local M = {}

local NB_CMD = "NB_EDITOR=: NO_COLOR=1 nb"

function M.get_nb_dir()
  return "/Users/iroiropro/ghq/github.com/zonehisa/nb"
end

function M.run_cmd(args)
  local cmd = NB_CMD .. " " .. args
  local output = vim.fn.systemlist(cmd)
  if vim.v.shell_error ~= 0 then
    return nil
  end
  return output
end

function M.parse_list_item(line)
  local note_id = line:match("^%[(.-)%]")
  if not note_id then
    return nil
  end

  local name = line:match("%[%d+%]%s*(.+)$")
  if not name then
    return nil
  end

  return {
    note_id = note_id,
    name = vim.trim(name),
    text = line,
  }
end

function M.list_items()
  local output = M.run_cmd("list --no-color")
  if not output then
    return nil
  end

  local items = {}
  for _, line in ipairs(output) do
    local item = M.parse_list_item(line)
    if item then
      table.insert(items, item)
    end
  end
  return items
end

function M.get_title(filepath)
  local nb_dir = M.get_nb_dir()
  if not filepath:match("^" .. vim.pesc(nb_dir)) then
    return nil
  end

  local file = io.open(filepath, "r")
  if not file then
    return nil
  end

  local first_line = file:read("*l")
  file:close()

  if first_line then
    return first_line:match("^#%s+(.+)")
  end
  return nil
end

function M.get_note_path(note_id)
  local output = M.run_cmd("show --path " .. note_id)
  if output and output[1] then
    return vim.trim(output[1])
  end
  return ""
end

function M.delete_note(note_id)
  local output = M.run_cmd("delete --force " .. note_id)
  return output ~= nil
end

function M.add_note(title)
  local trimmed = vim.trim(title or "")
  if trimmed == "" then
    return nil, "Title is empty"
  end

  local filename = os.date("%Y%m%d%H%M%S") .. ".md"
  local content = "# " .. trimmed .. "\n\n"
  local escaped_title = vim.fn.shellescape(trimmed)
  local escaped_filename = vim.fn.shellescape(filename)
  local escaped_content = vim.fn.shellescape(content)

  local output = M.run_cmd(
    "add --filename " .. escaped_filename ..
    " --title " .. escaped_title ..
    " --content " .. escaped_content
  )
  if not output then
    return nil, "Failed to add note"
  end

  local path = M.get_note_path(filename)
  if path == "" then
    return nil, "Failed to resolve note path"
  end
  return path
end

function M.import_image(source_path, filename)
  local src = vim.trim(source_path or "")
  if src == "" then
    return nil, "Image path is empty"
  end

  local dest = vim.trim(filename or "")
  if dest == "" then
    dest = vim.fs.basename(src)
  end

  local escaped_src = vim.fn.shellescape(src)
  local escaped_dest = vim.fn.shellescape(dest)
  local output = M.run_cmd("import " .. escaped_src .. " " .. escaped_dest)
  if not output then
    return nil, "Failed to import image"
  end

  return dest
end

function M.import_clipboard_image(filename)
  if vim.fn.executable("pngpaste") ~= 1 then
    return nil, "pngpaste is not installed"
  end

  local dest = vim.trim(filename or "")
  if dest == "" then
    dest = "clipboard-" .. os.date("%Y%m%d%H%M%S") .. ".png"
  end

  local tmp = "/tmp/" .. dest
  local escaped_tmp = vim.fn.shellescape(tmp)
  local paste_ok = vim.fn.system("pngpaste " .. escaped_tmp)
  if vim.v.shell_error ~= 0 then
    pcall(vim.fn.delete, tmp)
    return nil, "Clipboard does not contain an image"
  end

  local imported_name, err = M.import_image(tmp, dest)
  pcall(vim.fn.delete, tmp)
  if not imported_name then
    return nil, err
  end

  return imported_name
end

return M
