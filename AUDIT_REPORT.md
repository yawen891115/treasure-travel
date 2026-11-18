# Treasure Travel 代码核验与 Boston 实跑报告

日期：2026-11-18。原始附件保留；本版本为修复后的工作副本。

## 结论

已在云电脑实际完成：公开数据下载、Boston 市界筛选、清洗、PySpark ALS 训练、验证集选权重、测试集排序评测、约束重排、200 条模拟行程评测、Django 后端及真实 HTTP 请求测试。

**未完成/不能声称完成：真实 Claude 推理、Google Places/Routes 实时查询、Docker 容器启动、AWS 上线、真实用户 A/B 测试。** 没有调用付费 API，没有使用 GPU。新增的无密钥 planner 是确定性规则算法，不是 LLM。

## 数据与划分

- UCSD Google Local Massachusetts，数据快照采集截至 2021 年 9 月。
- 使用 Boston 官方 GIS 多边形，对经纬度执行 covers(Point)，严格 Boston 市区，不把 Cambridge/Somerville 算入。
- 初始合格 Boston POI 3,237 个；相关评论 582,361 条。
- 去重及 k-core 后：2,210 地点、22,287 公开评论者、352,408 交互。
- 训练 285,547、验证 22,287、测试 44,574 条。
- 每个用户最后两条为测试，前一条为验证，其余训练；相关性定义为评分 >=4。
- 从有正例的验证/测试用户各抽取最多 2,000 人；固定随机种子 42。
- 从完整 2,210 地点目录排序；验证排除训练已访问，测试排除训练及验证已访问；不是抽样负例小候选集。
- 模型权重只根据验证集选取；测试不用于权重搜索。

### 时序与泛化限制

这是**每用户时序切分**，不是全局同一时间截点。其他用户的训练交互可能晚于某用户的测试时点；静态 POI 描述/营业时间也不是每次访问当时的快照。k-core 与目录筛选使用全体观察交互。这些限制已明确记录，不能将此结果称为无泄漏的前瞻上线实验。评论也不等同于真实旅游行程。

## 实际排序结果

| 版本 | 验证 NDCG@5 | 测试 NDCG@5 | 测试目录覆盖率 |
|---|---:|---:|---:|
| 仅热度 | 0.0216 | 0.0311 | 0.59% |
| 热度+评分+TF-IDF | 0.0282 | 0.0334 | 14.43% |
| 基线+原始 ALS | 0.0477 | 0.0441 | 24.66% |
| 基线+去热度残差 ALS | **0.0480** | **0.0436** | **23.85%** |
| 仅 ALS，参考 | 0.0465 | 0.0440 | 25.34% |

按验证集选中的是“基线+去热度残差 ALS”。原始 ALS 版本测试略高，但没有因为看见测试结果就改选它。主结果相对三因素基线 NDCG@5 约提高 30.5%；这是该离线协议下的相对指标变化，不是用户满意度或点击率提升。

完整结果与权重：`results/ranking_results.json`、`results/ranking_results.md`。

## 200 条模拟行程的实跑

同一批 Boston 地点、相同请求与候选列表，比较固定 top-N 行程和新增规则 planner。地点为真实历史公开数据，请求为随机生成，不是真实客户。

| 指标 | 未检查约束的简单行程 | 约束感知规则 planner |
|---|---:|---:|
| 有非空行程 | 100% | 94% |
| 满足全部请求站点数 | 99% | 33% |
| 非空且满足评测约束 | 6.5% | 94% |
| **站点数完整且满足评测约束** | **6.5%** | **33%** |
| 违规、营业时间未知或无行程 | 93.5% | 6% |
| 平均站点数 | 3.99 | 2.42 |

规则 planner 对 200 条请求给出 188 条满足估算约束的非空行程，其中只有 66 条满足全部请求站点数。剩余 12 条无法生成方案。不能只写“违规率降到 0”而隐藏短行程/无方案。

使用历史营业时间、直线距离修正的交通时间和价格等级估计成本；不是实时地图价格或路线。规则 planner 本来就是按同一类约束构造结果，因此这是集成/可行性检查，不是独立证明推荐质量的试验。

完整逐条结果：`results/offline_rules_results.json`。约束重排：`results/rerank_results.md`。

## 验证记录

- 最终 Boston 数据运行：pytest **64 passed**；Django **12 passed**。
- Ruff 静态检查通过；Python compileall 通过。
- 真实本地 HTTP：主页 200、带 CSRF/session 的 chat 200、feedback 200、reset 200。
- 示例请求生成 3 站 Boston 行程，结果保存在 `audit/http_demo.json`。不应把历史地点信息当作今天的出行建议。
- Anthropic SDK 的工具调用协议通过本地 mock HTTP 服务器测试；不等于实际模型 API 已验证。
- 初始失败修复：SDK 测试被运行环境代理配置影响，改为本地 mock 时清理代理环境；此后通过。
- 初始普通 pip 安装遇到只读目录，改用工作区 venv 成功。
- 无 Docker 可执行程序，因此只检查配置，未执行镜像/容器验证。

## 修改位置与原因

| 文件 | 修改 |
|---|---|
| `src/ranker.py` | 保持精确同分顺序的 partition top-k 加速； 修复 k>=目录大小时越界；不足 k 个可推荐项以 -1 填充，不再推荐已看过或无效项；固定同分顺序。 |
| `src/metrics.py` | 短列表安全计算 NDCG；覆盖率排除 -1 填充值。 |
| `src/residualize.py` | 热度完全相同时避免除零/NaN。 |
| `src/als_spark.py` | 原先 1 星也被 implicit ALS 当正偏好；改为 rating-3 的正负强度，与 >=4 正例定义一致。 |
| `src/data_prep.py` | 修复词内子串误判（barber/parking/supermarket），使用完整词/词组匹配； k-core 迭代至收敛，修复迭代上限后的不满足阈值风险；空数据明确报错。 |
| `src/config.py` | 新增 TRAVEL_DATASET_ROOT，隔离不同数据集的数据、模型与结果。 |
| `src/constraints.py` | 费用分类同样使用完整词匹配，避免 parking 导致 art gallery 被当免费； 严格验证 HH:MM 范围，拒绝 10:99/25:00 等无效时间。 |
| `src/rerank.py` | 排除无效/填充 item；未知营业时间不再当作已确认营业。 |
| `src/serving.py` | 明确匿名文字查询 ranker 与离线个性化 ALS 不同，避免混用结果；修复 k<=0。 |
| `agent/tools.py` | 当前轮偏好写入有效约束；保留 budget=0；数值/工具参数校验、工具白名单、拒绝空行程。 |
| `agent/validator.py` | 未知营业时间单独标记为 unverified，而不是通过。 |
| `agent/maps.py` | google 模式缺 key 明确失败；无路线/无营业时间不默默降级成“实时确认”；路线分钟向上取整。 |
| `agent/llm.py` | 删除未经验证的默认 model ID，要求显式配置。 |
| `agent/offline.py` **新增** | 无密钥确定性 planner，检查营业窗口/行驶时间/路段上限/预算，未知条件向用户询问；与 LLM 明确区分。 |
| `scripts/01_prepare_boston.py` **新增** | 官方市界多边形筛选、Boston 数据生成与地理来源哈希记录。 |
| `scripts/download_public_data.py` **新增** | 官方源流式下载、校验及来源记录；可复现 Boston 数据。 |
| `scripts/02_rank_experiments.py` | 空评测集报错、机器可读结果、明确真实/合成及切分语义。 |
| `scripts/03_rerank_eval.py` | 不再把 after violation 硬编码为 0；实际重算，记录长度、无效项和未知营业时间。 |
| `scripts/04_make_test_requests.py` | 校验 n 与 survey 文件；示例合成问卷不再计作真实 survey。 |
| `scripts/survey_to_requests.py` | FAKE 示例标为 synthetic_example；找不到出发点则跳过，不随意替换为公园。 |
| `scripts/05_eval_agent.py` | 用数据/配置/代码指纹隔离缓存；异常计入分母；成本未配置时不编造估价；明确 fake 不是 AI 效果证据。 |
| `scripts/06_eval_offline.py` **新增** | 相同候选的确定性基线比较，保留所有失败/空结果；报告完整与部分行程、指纹及逐条结果。 |
| `scripts/smoke_http.py` **新增** | 可重复真实 localhost HTTP、CSRF、会话、反馈、重置 smoke test；强制 offline，避免意外调用付费 API。 |
| `scripts/check_llm.py` | 要求真实 model 配置；去掉未经核实的“只花几分钱”保证。 |
| `web/planner/views.py` | JSON 类型/长度/布尔校验；安全 503；偏好传递；保留上一轮行程上下文；新增 offline 后端。 |
| `web/planner/templates/planner/index.html` | 重复点击与 reset 竞态保护、错误提示、offline 模式标识及 Boston 输入示例。 |
| `web/travel_site/settings.py` | 生产弱密钥拒绝启动、后端配置校验、请求体限制；无 key 默认 offline。 |
| `tests/` 与 `web/planner/tests.py` | 新增/扩展回归测试，覆盖上述边界和离线 planner，测试本地 SDK 协议。 |
| `.env.example` | 清空 key/model/价格占位，避免把未验证模型或价格当可用配置。 |
| `requirements.txt` / `requirements-audit-lock.txt` | Boston polygon 增加 Shapely；记录本次实际测试的直接依赖版本。 |
| `.github/workflows/tests.yml` | 在 CI 流程加入无 API 的离线 planner 评测。 |
| `.dockerignore` | 排除 audit 数据与中间 Boston 数据，防止误入部署镜像。 |
| `README.md` | 更新实测结果、无 key 操作、数据来源、复现命令与限制，不宣称实际 AWS 上线。 |

逐行补丁见 `AUDIT_CHANGES.patch`；代码和证据文件哈希见 `audit/deliverable_manifest.json`。

## 仍然存在的明确边界

1. 真实 LLM/Google Maps API 尚未实测；启用前需有效 key、可用 model、账单预算及安全配置。
2. 没有真实 App 用户、500 份问卷、Product Hunt 1,000 用户或 AWS 上线证据，不能从本代码运行反推这些历史。
3. Web 无身份认证/配额控制；不能直接将付费 key 放到公开服务后当作生产可用。
4. 规则 planner 是贪心且英语受限语法；不做通用中文理解/地址地理编码，默认单站 60 分钟，可能仅给出部分行程。
5. 用户兴趣多样性、行程满意度、线上点击率未评测；三家咖啡店的可行路线不等于最好的旅游行程。
6. 实时 Maps 代码仍需验证节假日/特殊营业时间、缓存更新策略和网络失败路径；本次没有把这些静态检查当作线上验证。

## 可以据实使用的简历表述

- Built and evaluated a Boston place-ranking pipeline on 285K public training interactions across 2,210 POIs; validation-selected TF-IDF/popularity + popularity-residualized PySpark ALS improved test NDCG@5 from 0.0334 to 0.0436 and catalog coverage from 14.43% to 23.85% on 2,000 held-out reviewers.
- Implemented a Django trip planner with a deterministic no-key fallback and regression coverage; on 200 simulated Boston requests, generated 188 nonempty plans satisfying historical-hours and estimated travel/budget constraints, with 66 fulfilling all requested stops.

这两条只描述本次可验证技术成果；不代替对创业身份、时间线、真实用户规模的单独确认。
