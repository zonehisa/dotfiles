return {
  'mattn/emmet-vim',
  ft = { 'html', 'css', 'javascript', 'typescript', 'javascriptreact', 'typescriptreact', 'vue' },
  init = function()
    vim.g.user_emmet_leader_key = '<C-z>'  -- Ctrl+z に変更（Ctrl+eはabortで使用中）
  end,
}
