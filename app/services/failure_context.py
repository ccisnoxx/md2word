"""转换与渲染共用的异常定位附加合同，不改变原异常类型。"""
from typing import Any


FAILURE_CONTEXT_ATTRIBUTE = "md2word_failure_context"


def attach_failure_context(error: BaseException, **context: Any) -> None:
    """把失败操作定位挂到异常上；已有（更内层）上下文时保留原值。执行层只读取并白名单过滤。"""
    if getattr(error, FAILURE_CONTEXT_ATTRIBUTE, None) is None:
        setattr(error, FAILURE_CONTEXT_ATTRIBUTE, context)
