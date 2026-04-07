local function pick_notes()
  local nb = require("config.nb")
  local Snacks = require("snacks")
  local items = nb.list_items()
  if not items or #items == 0 then
    vim.notify("No notes found", vim.log.levels.WARN)
    return
  end

  Snacks.picker({
    title = "nb Notes",
    items = items,
    format = function(item)
      return { { item.text } }
    end,
    preview = function(ctx)
      local item = ctx.item
      if not item.file then
        item.file = nb.get_note_path(item.note_id)
      end
      return Snacks.picker.preview.file(ctx)
    end,
    confirm = function(picker, item)
      picker:close()
      if item then
        vim.cmd.edit(nb.get_note_path(item.note_id))
      end
    end,
    actions = {
      delete_note = function(picker)
        local item = picker:current()
        if item then
          vim.ui.select({ "Yes", "No" }, { prompt = "Delete: " .. item.name .. "?" }, function(choice)
            if choice == "Yes" then
              if nb.delete_note(item.note_id) then
                vim.notify("Deleted: " .. item.name, vim.log.levels.INFO)
                picker:close()
                pick_notes()
              else
                vim.notify("Failed to delete", vim.log.levels.ERROR)
              end
            end
          end)
        end
      end,
    },
    win = {
      input = {
        keys = {
          ["<C-d>"] = { "delete_note", mode = { "n", "i" } },
        },
      },
    },
  })
end

local function grep_notes()
  local nb = require("config.nb")
  local Snacks = require("snacks")
  Snacks.picker.grep({
    dirs = { nb.get_nb_dir() },
  })
end

local function add_note()
  local nb = require("config.nb")
  vim.ui.input({ prompt = "Note title: " }, function(title)
    if not title or vim.trim(title) == "" then
      return
    end

    local path, err = nb.add_note(title)
    if not path then
      vim.notify(err or "Failed to add note", vim.log.levels.ERROR)
      return
    end

    vim.cmd.edit(path)
  end)
end

local function import_image()
  local nb = require("config.nb")
  local default_name = "clipboard-" .. os.date("%Y%m%d%H%M%S") .. ".png"
  vim.ui.input({ prompt = "Saved filename: ", default = default_name }, function(filename)
    if filename == nil then
      return
    end

    local imported_name, err = nb.import_clipboard_image(filename)
    if not imported_name then
      vim.ui.input({ prompt = "Image path: " }, function(source_path)
        if not source_path or vim.trim(source_path) == "" then
          vim.notify(err or "Failed to import image", vim.log.levels.ERROR)
          return
        end

        local path_default_name = vim.fs.basename(vim.trim(source_path))
        local final_name = vim.trim(filename) ~= "" and filename or path_default_name
        imported_name, err = nb.import_image(source_path, final_name)
        if not imported_name then
          vim.notify(err or "Failed to import image", vim.log.levels.ERROR)
          return
        end

        local markdown = string.format("![%s](%s)", imported_name, imported_name)
        local row, col = unpack(vim.api.nvim_win_get_cursor(0))
        vim.api.nvim_buf_set_text(0, row - 1, col, row - 1, col, { markdown })
      end)
      return
    end

    local markdown = string.format("![%s](%s)", imported_name, imported_name)
    local row, col = unpack(vim.api.nvim_win_get_cursor(0))
    vim.api.nvim_buf_set_text(0, row - 1, col, row - 1, col, { markdown })
  end)
end

return {
  "folke/snacks.nvim",
  keys = {
    { "<leader>na", add_note, desc = "nb add note" },
    { "<leader>ni", import_image, desc = "nb import image" },
    { "<leader>np", pick_notes, desc = "nb picker" },
    { "<leader>ng", grep_notes, desc = "nb grep" },
  },
}
