# 诗笺 变更史与技术细节（从 project skill 迁出，2026-11-05）

- 2026-11-03 源码迁入；tools/*.py 路径改为本项目路径。
- 分享海报：诗页「分享」弹 canvas 海报（整首诗，页脚「诗」印+诗笺+shijian.jisu.cn），下载/分享链接/×；绘制前等 ShiciSerif 子集加载。
- 古人说：最初集成 gu-ren-said（MIT），v22 起改为自建句库：tools/said_src.txt（标签|原句|作者）→ said_build.py 在 corpus 核对 → app/site/said.json（kw 现代说法→标签，cw 标签→古语，q 句子含篇目 id）。前端 saidMatch 本地匹配，不足 3 条 saidWide 全站兜底（意思→二字组→单字）。加句子：改 said_src.txt 跑 said_build.py，升 said.json?v=。
- v18 先唐诗 xiantang（werneror/ Werneror/Poetry MIT）、先秦两汉典籍 dianji（prose-classics/*.json，prose=True）。
- v19 金元明清（jinyuan/mingshi/qingshi）；作者朝代归一（load.py DYN_NORM/GENERIC/ADJ，报告 build/dyn_report.json）。站点 545MB，目录部署超时 → 先 zip 到 /tmp/app.zip 再 makers deploy /tmp/app.zip（约 8 分钟；CLI 可能被 1200s 截断但服务端照常完成）。
- Turso 开放 API：tools/turso_build.py（先 pack 到 build/cc 或 CC_PACK=build/cc2，再建库约 2 分钟，FTS5 外部内容表 works_grams 二字组）。上传：删库→建库 seed database_upload→POST /v1/upload，上传前 PRAGMA journal_mode=WAL，库须为空。重建后重新生成全权限/只读 token（只读 token 在 app/lib，变了要重新部署）。现库 shijian-v2（org jisu，东京），884,767 篇，由仓库 887ea3fc 生成。API id ≠ 站点 id（静夜思 API 42478 / 站点 41910；李白 API 2682 / 站点 2692）。build/cc 为旧快照供 load.py buyi 用，勿覆盖。不要与 emit/index 并行（OOM）。
- v20 关于页数据源只写 chinese-classics；去重：同作者同题正文差≤10% 视为重复。
- v21 按篇朝代（pop.json dl+db）；buyi 历代补遗。load.py 需 pip install opencc numpy。
- v23 buyi 全文去重；全站 861,357。
- v24 关于页合集篇数（tools/cats.py，emit 后运行，读 chinese-classics/ 克隆，慢，后台跑）。
- v24b/v26 404 与 API 文档/调试台为 app.js 站内路由（#/api、#/api/test、#/404）；/api/v1 浏览器 302 /#/api/test；云函数跳转用相对 location。
- 仓库同步：tools/repo_sync.py（项目根 chinese-classics/ 克隆），提交 887ea3fc 已推送 wujinpai/chinese-classics。git push 用 credentials [{provider:"github-git"}]。
- v27 历代补遗并入各合集（meta mc + ext，ids 从 868000 起）；site/data/moved.json（tools/moved.py）旧 id→新 id，前端自动跳转。构建顺序：load → emit → index → said_build → cats → moved。
- v28 去掉 AI 释义/简介；开放 API 迁到 app/edge-functions/，共用 app/lib/。
- v29 维基作者简介 5,170 位（tools/wiki_bios.py，CC BY-SA 署名）；剩 12,918 位无简介。
- v31 EdgeOne 站点加速（zone-3uu4zgt2ynxe 免费版）；tools/teo.py 调腾讯云 API（密钥 .secrets/tencent-api）。
- v32（dpqyynmm815q）si.jisu.cn 舍弃，链接改回 shijian.jisu.cn；si 加速域名已删。
- v33（dpkehht92jsi）PC 顶栏三栏网格（>640px：1fr|520px|1fr），左右与卡片对齐；app.css v=18、SHELL v33。
- 2026-11-05 进行中：异作者同文去重（1,289 组，build/attrib/groups.json → 子代理输出 out0-5.json），之后改站点 + API + 仓库。

## v34（2026-11-06）异作者同文去重 + 异名归并（站点 / API / 仓库同一套判定）
- 判定：build/attrib/out0-5.json（站点 1,289 组）、o2_0-5.json（groups2 1,255 组；o2_3 由 tools/o2_3_gen.py 生成）、alias_auto.json（tools/alias_collect.py 从判定里收集的同人异名，176 条，已剔除李彭/钱起等真实他人）。
- 站点：tools/attrib_fix.py → emit → index → said_build → moved → cats（cats 读仓库，约 6 分钟，单独后台跑）。删 1,353 篇，merged.json 旧 id→保留 id。部署 dpo7akgsjwdc。
- API：tools/api_fix.py plan/apply（组内去重，写 merged 表）+ tools/api_fuzzy.py / api_fuzzy_plan.py（异体字近似重复，能对上站点判定或只有一个具名作者的 140 组）+ tools/api_fix_finish.py（异名按 author_id 归并、统计）。works 884,767 → 882,486；/api/v1/poems/{旧id} 301。works.author 无索引，按 author 全表更新会超时。
- 仓库：tools/repo_attrib.py（保留原 JSON 格式、只写改动文件，近似匹配），提交 1648f126：删 2,008 首、211 个作者文件改名/并入。
- 未完成：API 还有约 1,979 组异体字近似重复（build/attrib/fuzzy_api_left.json）未判定；站点同类近似重复未扫。

## v35（2026-11-06）三方统一：仓库为唯一数据源（用户：只要数据统一、不重复）
- 仓库 acac639c（main）：786,371 条（作品 + 典籍章节）。删 97,362 条：同作者正文全同或异体字差≤10%（≥10 字）、正文全同异作者（留有站点对应且作者一致的，具名优先于佚名）、「二首」等整组合抄与分首并存（删合抄，留分首）、空/不足 4 字条目；典籍章节与作者文件重复的留章节（《大学》《中庸》等）。
- 作者名：同人异写先归一（tools/repo_canon.py 的 GX 显式表 + STDV 异体字表：陶潜→陶渊明、无名氏/不详/阙名→佚名、晁逈→晁迥 等）；其余冲突默认按仓库，例外（仓库名含 ?□/截断/疑似误析/站点为原字异写）用站点名。古文观止章节作者去掉「先秦：」前缀，诗经作者 佚名，文字蒙求作者 王筠。
- 通行本：站点组里有唐诗三百首/宋词三百首/水墨唐诗/千家诗的版本时用其文字并回写仓库（221 处，如《静夜思》床前明月光、《赤壁》折戟沉沙），其余文字用仓库版。标题用仓库（合并组取最完整的标题）。
- 流程：tools/v35_run.sh（clone 1648f126 → repo_canon plan/apply → canon（报站点独有）→ addsite → textfix → canon 校验）；校验 tools/v35_verify.py（站点与仓库键逐条一致、无全同重复）。
- 站点：新阶段 tools/canon.py（attrib_fix 之后、emit 之前；读 *.pre_canon.* 可重跑）。786,371 篇，并掉 73,659 条（含空 565）写 merged.json；千家诗、水墨唐诗改为选本（x.ls → l/qjs.json、l/shuimo.json）；合集篇数按实际记录数（emit）；cats 用 REPO_READ=/tmp/cc/chinese-classics。app.js v33、DV v15、SHELL v35、DATA v15。首页统计改「首选本名篇」。
- API：tools/api_sync.py plan/apply（可续跑，进度 build/consist/api_sync_progress.json，tools/api_sync_run.sh）。保留已有 id：更新 24,262、删 97,086（96,836 写 merged 表跳转，合抄跳第一首；250 条无对应）、新增 971（id 从 884768 起）。
- 遗留：工作区 chinese-classics/ 克隆是旧版（JuiceFS 太慢），用前 git fetch && git reset --hard origin/main 或直接在 /tmp clone。
- 2026-11-06 v35 API 同步完成：works 786371 authors 30990，与仓库/站点一致
- 2026-11-06 v35 校验的 20 对作者键差为误报：v35_verify 读仓库作者时经 s2 繁转简把人名里的「乾」转成「干」、𢍰→𪪴；仓库原文、站点、API 均为 源乾曜/娄乾曜/曾乾曜/卢乾元/乾道民谣/赵师𢍰，三方一致，无需改数据。
- 2026-11-06 API 修古文观止章节作者被套「清」：47 个重复作者并回本人（如清·李白→唐李白），12 个无同名者改正朝代；作者 30990→30943。脚本 tools/api_guwen_fix.py，api_sync 后需重跑。陶渊明(古文观止)与陶潜(诗) 仍是两条作者记录，仓库/站点同此。
- 2026-11-06 用户规则：同一作者的不同写法（本名/字号、繁简、带「撰」「朝代·」前缀、不详/无名氏）必须三方统一成一个名字，直接做，不用问。
## v36（2026-11-06）作者同人异名归一（用户：作者名必须统一，不用问）
- 仓库 9cee5450→47f3eba9→200c87ad→98423e95：tools/alias_merge.py 归一 陶潜→陶渊明、不详/无名氏→佚名、宋代庙号→本名（宋度宗/赵祺→赵禥）、玄宗皇帝李隆基/南唐嗣主李璟/章怀太子/宋蒲寿宬/释仲殊、22 组异体字同人（取有小传的全宋诗原字：赵汝𬭼、戴昺、钱勰、蔡柟…）、古文观止「刘向 撰」「西晋·李密」；并后同人近似重复（≥90%）去 424 条；赵佶朝代 金→宋。785,947 条。
- 站点：repo_canon.GX 加 v36 映射；canon.py 加 NEAR90 配对（同作者 ≥90%）。785,947 篇。app.js v34、DV v16、SHELL v36、DATA v16。
- API：tools/api_alias.py（改名/并作者、删近似重复写 merged、重算计数）＋ api_guwen_fix。785,947 篇，作者 30,901。
- 未动：截断名（曾/王/李…宋词）、括注区分同名（王佐（汝学 等）、有争议的异作者组、清诗陈珏（另一人）。

## v37（2026-11-06）去掉 # 路由
- 前端改 History 路由：/p/123、/c/x、/a/…、/s?q=、/said、/authors、/fav、/about、/api、/api/test、/404。站内点击由全局 click 拦截 pushState，popstate 回退。
- edgeone.json 加 SPA fallback rewrite（/* → /index.html），删 site/404.html 与 edge-functions/api/index.js（/api 走 SPA）。
- 旧 #/ 链接按用户要求不跳转，直接显示 404。/api/v1 浏览器 302 /api/test；未知接口 302 /404。api.html 仅在 .html 路径下跳 /api。
- app.js v36、SHELL v38。api.html 改名 api-doc.html（Makers 会把 /api 映射到 api.html）。

## v38/v39（2026-11-06）
- 文件数超 Makers 上限：分片合并 p PS=500、s CH=2000、索引 i 512 片，部署约 4,132 文件。
- AI 按需：/api/ai/poem?id=、/api/ai/author?a=&d=（lib/ai.js，模型 @makers/deepseek-v4-flash，thinking disabled，6–9 秒；结果 CDN+内存缓存）。前端点击按钮才调用，标「AI 生成，仅供参考」。
- 简介占位「--」「无传。」（约 2,100 位）视作无简介，显示 AI 按钮（realBio）。
- 线上 dp1xse0ghbms：app.js v39、SHELL v40、DV v17、app.css v19。
