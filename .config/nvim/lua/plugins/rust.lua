return {
  {
    "mfussenegger/nvim-dap",
    lazy = true,
  },
  {
    "mrcjkb/rustaceanvim",
    version = "^6",
    lazy = false,
    dependencies = {
      "mfussenegger/nvim-dap",
      "neovim/nvim-lspconfig",
    },
    init = function()
      local lsp = require("config.lsp")

      vim.g.rustaceanvim = {
        tools = {
          hover_actions = {
            auto_focus = true,
          },
          code_actions = {
            ui_select_fallback = true,
          },
          test_executor = "background",
        },
        server = vim.tbl_deep_extend("force", lsp.default_config(), {
          on_attach = function(client, bufnr)
            lsp.on_attach(client, bufnr)
            lsp.enable_inlay_hints(client, bufnr)

            local function opts(desc)
              return { buffer = bufnr, silent = true, desc = desc }
            end

            vim.keymap.set("n", "K", "<cmd>RustLsp hover actions<cr>", opts("Rust hover actions"))
            vim.keymap.set("n", "<leader>ca", "<cmd>RustLsp codeAction<cr>", opts("Rust code action"))
            vim.keymap.set("n", "<leader>rr", "<cmd>RustLsp runnables<cr>", opts("Rust runnables"))
            vim.keymap.set("n", "<leader>rt", "<cmd>RustLsp testables<cr>", opts("Rust testables"))
            vim.keymap.set("n", "<leader>rd", "<cmd>RustLsp debuggables<cr>", opts("Rust debuggables"))
            vim.keymap.set("n", "<leader>re", "<cmd>RustLsp explainError current<cr>", opts("Rust explain error"))
            vim.keymap.set("n", "<leader>rE", "<cmd>RustLsp renderDiagnostic current<cr>", opts("Rust render diagnostic"))
            vim.keymap.set("n", "<leader>rm", "<cmd>RustLsp expandMacro<cr>", opts("Rust expand macro"))
          end,
          default_settings = {
            ["rust-analyzer"] = {
              cargo = {
                allFeatures = true,
                buildScripts = {
                  enable = true,
                },
              },
              procMacro = {
                enable = true,
              },
              checkOnSave = true,
              check = {
                command = "clippy",
                extraArgs = { "--all-targets" },
              },
              diagnostics = {
                experimental = {
                  enable = true,
                },
                styleLints = {
                  enable = true,
                },
              },
              hover = {
                actions = {
                  enable = true,
                  debug = {
                    enable = true,
                  },
                  implementations = {
                    enable = true,
                  },
                  references = {
                    enable = true,
                  },
                  run = {
                    enable = true,
                  },
                },
              },
              lens = {
                enable = true,
                debug = {
                  enable = true,
                },
                implementations = {
                  enable = true,
                },
                references = {
                  adt = {
                    enable = true,
                  },
                  enumVariant = {
                    enable = true,
                  },
                  method = {
                    enable = true,
                  },
                  trait = {
                    enable = true,
                  },
                },
                run = {
                  enable = true,
                },
              },
              inlayHints = {
                bindingModeHints = {
                  enable = true,
                },
                closureCaptureHints = {
                  enable = true,
                },
                closureReturnTypeHints = {
                  enable = "with_block",
                },
                discriminantHints = {
                  enable = "fieldless",
                },
                expressionAdjustmentHints = {
                  enable = "reborrow",
                },
                lifetimeElisionHints = {
                  enable = "skip_trivial",
                },
                parameterHints = {
                  enable = true,
                },
                rangeExclusiveHints = {
                  enable = true,
                },
                typeHints = {
                  enable = true,
                  hideClosureInitialization = false,
                  hideNamedConstructor = false,
                },
              },
              semanticHighlighting = {
                operator = {
                  enable = true,
                  specialization = {
                    enable = true,
                  },
                },
                punctuation = {
                  enable = true,
                  separate = {
                    macro = {
                      bang = true,
                    },
                  },
                },
              },
            },
          },
        }),
      }
    end,
  },
  {
    "saecki/crates.nvim",
    event = { "BufRead Cargo.toml", "BufNewFile Cargo.toml" },
    tag = "stable",
    dependencies = {
      "nvim-lua/plenary.nvim",
    },
    config = function()
      require("crates").setup({
        popup = {
          border = "rounded",
        },
      })

      vim.api.nvim_create_autocmd({ "BufReadPost", "BufNewFile" }, {
        pattern = "Cargo.toml",
        callback = function(args)
          local crates = require("crates")

          local function call(fn_name)
            return function()
              local fn = crates[fn_name]
              if fn then
                fn()
                return
              end

              vim.notify("crates.nvim: `" .. fn_name .. "` is unavailable", vim.log.levels.WARN)
            end
          end

          local function opts(desc)
            return { buffer = args.buf, silent = true, desc = desc }
          end

          vim.keymap.set("n", "<leader>cp", call("show_popup"), opts("Cargo show crate popup"))
          vim.keymap.set("n", "<leader>cu", call("update_crate"), opts("Cargo update crate"))
          vim.keymap.set("n", "<leader>cU", call("upgrade_crate"), opts("Cargo upgrade crate"))
          vim.keymap.set("n", "<leader>cA", call("upgrade_all_crates"), opts("Cargo upgrade all crates"))
          vim.keymap.set("n", "<leader>cr", call("reload"), opts("Cargo reload crates"))

          local ok, cmp = pcall(require, "cmp")
          if ok then
            cmp.setup.buffer({
              sources = cmp.config.sources({
                { name = "crates" },
              }, {
                { name = "nvim_lsp" },
                { name = "buffer" },
              }),
            })
          end
        end,
      })
    end,
  },
}
