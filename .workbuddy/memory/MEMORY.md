# Listing Generator — 项目长期笔记

## 项目定位
AI Amazon Listing 图片 Agent（SKILL.md = "AI E-commerce Listing Agent V2"）。用户给一个产品（图/文字），产出：产品分析 → 证据分级 → 卖点 → 转化驱动力 → H1-H5 图片规划（可扩展 PDP D1-D9）→ 模板选择 → Campaign Style Lock → 英文 Prompt → （确认后）批量出图 → QA。

## 关键文件
- SKILL.md：完整行为规范（59 节），工作中必须遵守。
- scripts/generate_image.py：生图脚本；sync（OpenAI 兼容）/ async（apimart）自动检测；参数 --prompt-file / --image / --size / --resolution / --output-dir；配置走 .env（IMG_BASE_URL、IMG_MODEL、IMG_API_KEY，兼容 OPENAI_* 别名）。
- scripts/listing_plan.py：`python listing_plan.py <draft.json> -o listing_plan.json`；校验证据等级、高风险 claims（tpu/shockproof/防水 等）、模板 ID 存在性、H1-H5 顺序。
- references/templates/：25 个模板 JSON（01-hero-image … 25-sports-campaign），只按需读取，不要一次全读。

## 硬规则
- 默认 Planning Mode；只有用户明确"生成/出图"才进 Generate Mode。
- Evidence Gate：confirmed / inferred / unknown，禁止把推断写成产品事实；高风险 claims（材质、防水防摔、认证、兼容性等）无证据不得进图片文字。
- Campaign Style Lock 贯穿整套图；Amazon 主图纯白 #FFFFFF、无文字无装饰。
- Image QA：Hard Fail 必须修；重试上限 MAX_RETRY=3。
- 输出目录：generated-images/{product-slug}-amazon-listing/，文件名 H1-hero.png 等。

## 环境备注（2026-09-14）
- 项目无 .env（根目录/Desktop/用户主目录都没有）→ 脚本生图不可直接用；优先用本环境内置图片生成能力（SKILL.md 36.0 Provider 第 1 优先级）。
- 已完成案例：cute-apple-phone-case（白壳红苹果贴纸手机壳）H1-H5 五张，位于 generated-images/cute-apple-phone-case-amazon-listing/。

## 用户偏好
（待补充：称呼、常用品类、品牌规范等）
