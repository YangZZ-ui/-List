"""
客户沟通模块
实现常见问询自动回复与开放性问题智能应答
所有回复内置审计边界保护与免责声明，维护安永独立性原则
"""

import os
import sys
from typing import Dict, Any, Optional
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import EY_DISCLAIMER, HAS_AI, OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL


# ---------- 问询模板库 ----------
INQUIRY_TEMPLATES = {
    "audit_progress": {
        "keywords": ["进度", "进展", "status", "progress", "做到哪", "阶段"],
        "title": "审计进度说明",
        "response": (
            "感谢您对我们审计工作的关注。"
            "目前项目正处于 {phase} 阶段，预计在 {expected_date} 完成本阶段工作。"
            "具体时间表可能因资料完整性及进一步询问的需要而调整。"
            "如您有任何补充资料，请随时提供，这将有助于我们高效推进。"
        ),
    },
    "document_list": {
        "keywords": ["资料", "清单", "document", "资料清单", "需要什么", "提供什么"],
        "title": "所需资料清单",
        "response": (
            "根据当前审计范围，我们还需要贵司协助提供以下资料：\n\n"
            "1. {period} 期间的银行对账单及余额调节表；\n"
            "2. 期末存货盘点表及盘点差异说明；\n"
            "3. 重大合同及协议（金额超过 {threshold} 的）；\n"
            "4. 关联方交易明细及定价政策说明；\n"
            "5. 诉讼、索赔及或有事项清单。\n\n"
            "如您已准备部分资料，可优先提供，我们将及时更新收取记录。"
        ),
    },
    "variance_explanation": {
        "keywords": ["差异", "variance", "变动", "为什么", "原因", "解释", "波动"],
        "title": "差异解释请求",
        "response": (
            "我们在分析过程中注意到以下差异/变动，恳请贵司协助解释：\n\n"
            "- **关注领域**：{area}\n"
            "- **观察到的差异**：{observation}\n"
            "- **期望的解释**：包括但不限于业务背景、会计处理依据、支持性文件等。\n\n"
            "请您在 {deadline} 前提供书面说明及相关支持文件，以便我们及时完成审计程序。"
        ),
    },
    "fee_billing": {
        "keywords": ["费用", "fee", "账单", "invoice", "billing", "报价", "收费"],
        "title": "审计费用与账单",
        "response": (
            "关于审计费用的具体事宜，请联系项目负责合伙人或经理。"
            "费用安排基于审计范围、复杂程度及预计工时确定，"
            "任何范围变更都可能导致费用调整。"
            "我们不会在未提前沟通的情况下增加额外收费项目。"
        ),
    },
    "report_timeline": {
        "keywords": ["报告", "report", "什么时候出", "出具", "签发", "发布时间"],
        "title": "报告出具时间",
        "response": (
            "审计报告的出具时间取决于以下关键因素：\n\n"
            "1. 贵司提供完整、准确的审计资料的时间；\n"
            "2. 我们对发现问题的沟通与解决进度；\n"
            "3. 内部质量复核程序的完成时间。\n\n"
            "基于当前计划，我们预计于 {expected_date} 出具草稿报告供贵司审阅。"
            "最终报告将在贵司确认草稿并完成所有必要程序后签发。"
        ),
    },
}


def classify_inquiry(text: str) -> Optional[str]:
    """根据关键词匹配问询类型"""
    text_lower = text.lower()
    for key, template in INQUIRY_TEMPLATES.items():
        if any(kw in text_lower for kw in template["keywords"]):
            return key
    return None


def fill_template(template_key: str, context: Dict[str, Any]) -> Dict[str, str]:
    """填充模板变量，生成标准化回复"""
    tmpl = INQUIRY_TEMPLATES.get(template_key)
    if not tmpl:
        return {"title": "未匹配模板", "content": ""}

    # 提供默认值
    defaults = {
        "phase": "外勤执行",
        "expected_date": "待定",
        "period": "本期",
        "threshold": "重要性水平",
        "area": "待指定",
        "observation": "待补充",
        "deadline": "五个工作日内",
    }
    defaults.update(context)

    try:
        content = tmpl["response"].format(**defaults)
    except KeyError:
        content = tmpl["response"]

    return {
        "title": tmpl["title"],
        "content": content,
        "type": "template",
    }


def _call_llm_for_client(question: str, context: str = "") -> Optional[str]:
    """调用大模型回答开放性客户问题（严格限制审计边界）"""
    if not HAS_AI:
        return None

    try:
        import openai
        client = openai.OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
        system_prompt = (
            "你是一位安永会计师事务所的客户服务代表，负责回复客户的日常问询。"
            "你的回答必须满足以下约束：\n"
            "1. 不得给出任何审计意见、保证或专业结论；\n"
            "2. 不得代替审计师做出判断或决策；\n"
            "3. 涉及审计发现、差异或调整的问题，必须引导客户与项目审计团队直接沟通；\n"
            "4. 语气专业、礼貌、简洁；\n"
            "5. 使用中文回复。"
        )
        user_prompt = f"客户问题：{question}\n"
        if context:
            user_prompt += f"\n项目背景：{context}\n"
        user_prompt += "\n请直接给出回复正文，不要添加问候语之外的额外格式。"

        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=1500,
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"客户沟通 AI 调用失败：{e}")
        return None


def generate_client_response(
    question: str,
    context: Dict[str, Any] = None,
    use_ai: bool = True,
) -> Dict[str, str]:
    """
    生成客户问询回复
    优先匹配模板 -> 其次调用 AI -> 最后返回通用引导
    """
    context = context or {}

    # 1. 尝试模板匹配
    matched_type = classify_inquiry(question)
    if matched_type:
        result = fill_template(matched_type, context)
        result["content"] += f"\n\n---\n{EY_DISCLAIMER}"
        return result

    # 2. 尝试 AI 回复（开放性询问）
    if use_ai and HAS_AI:
        ai_reply = _call_llm_for_client(question, context.get("project_summary", ""))
        if ai_reply:
            return {
                "title": "智能回复",
                "content": f"{ai_reply}\n\n---\n{EY_DISCLAIMER}",
                "type": "ai",
            }

    # 3. 通用引导回复
    return {
        "title": "问询已收到",
        "content": (
            "感谢您的问题。为确保回复的准确性与专业性，"
            "我们已将您的问询转交项目审计团队，相关负责人员将于两个工作日内与您联系。\n\n"
            f"如您的问题较为紧急，请直接联系项目现场负责人。\n\n---\n{EY_DISCLAIMER}"
        ),
        "type": "fallback",
    }
