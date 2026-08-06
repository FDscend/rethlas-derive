"""命题推导工具核心库。

CLI 是外层接口；core 负责：
- config   : 统一配置（config.yaml + CLI 覆盖）
- workspace: 命题 id / checkpoint / 目录管理
- codex    : codex exec 封装（含 Windows 平台兼容）
- search   : TheoremSearch 搜索 + arXiv TeX 源下载
- pdf      : PDF 提取（MinerU -> .env python -> PyMuPDF 降级链）
- verify   : 自然语言验证（独立 codex 会话）
- derive   : 推导循环编排（搜索 -> 生成 -> 验证 -> 迭代）
- agent_mcp: 内部 MCP server（供生成/验证 agent 使用 memory/search/download）
"""
