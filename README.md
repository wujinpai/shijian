# shijian
收录自先秦至近现代的中华古诗词全集，涵盖诗经、楚辞、唐诗、宋词、元曲及近现代旧体诗词，持续整理与校勘。

## 目录
- `app/`：EdgeOne Makers 部署根。`site/` 静态站（含 `data/` 分片数据、检索索引），`edge-functions/` 开放 API，`lib/` 共用代码；数据库连接取 Makers 项目环境变量 `TURSO_URL`、`TURSO_TOKEN`（只读）。
- `tools/`：数据构建脚本（load → attrib_fix → canon → emit → index → said_build → moved → cats），数据源为 [chinese-classics](https://github.com/wujinpai/chinese-classics)。
- `HISTORY.md`：版本记录。
- 线上：https://shijian.jisu.cn
