"""
冷启动预测API路由
提供学生成绩预测服务
"""

import asyncio
import time
from fastapi import APIRouter, HTTPException, Request
from loguru import logger

from src.schemas.cold_start import (
    ColdStartRequest,
    ColdStartResponse,
    SubjectScore,
    ColdStartPrediction
)
from src.code_start.predictor import StudentProfile
from src.code_start.formatter import ResultFormatter

router = APIRouter(tags=["cold-start"])

# 最小响应时间（秒），用于前端进度条动画
MIN_RESPONSE_TIME = 1.0


def _to_profile(request: ColdStartRequest) -> StudentProfile:
    """将请求转换为StudentProfile"""
    return StudentProfile(
        gender=request.gender,
        grade=request.grade,
        daily_study_time=request.daily_study_time,
        math_recognition=request.math_recognition,
        learning_autonomy=request.learning_autonomy,
        learning_perseverance=request.learning_perseverance,
        learning_curiosity=request.learning_curiosity,
        current_goal=request.current_goal
    )


def _to_response(profile: StudentProfile, result, message: str = None) -> ColdStartResponse:
    """将预测结果转换为响应"""
    persona_text = ResultFormatter.to_persona_text(profile, result)

    return ColdStartResponse(
        success=True,
        data=ColdStartPrediction(
            math=SubjectScore(score=result.math_score, level=result.math_level),
            reading=SubjectScore(score=result.reading_score, level=result.reading_level),
            science=SubjectScore(score=result.science_score, level=result.science_level)
        ),
        persona_text=persona_text,
        message=message
    )


@router.post("/api/cold-start/predict", response_model=ColdStartResponse)
async def predict_score(request: ColdStartRequest, req: Request):
    """
    预测学生成绩

    根据学生的学习行为和态度特征，预测数学、阅读、科学三科成绩
    响应时间至少为2秒，用于前端进度条动画展示
    """
    logger.info(f"[COLD_START] 收到预测请求: gender={request.gender}, grade={request.grade}")

    start_time = time.time()

    try:
        # 从app state获取预测器
        predictor = req.app.state.cold_start_predictor

        if predictor is None:
            raise HTTPException(status_code=503, detail="预测模型未加载")

        # 执行预测
        profile = _to_profile(request)
        result = predictor.predict(profile)

        logger.info(f"[COLD_START] 预测完成: math={result.math_score:.2f}, "
                   f"reading={result.reading_score:.2f}, science={result.science_score:.2f}")

        # 计算已用时间
        elapsed_time = time.time() - start_time

        # 如果响应时间小于最小时间，则延迟返回
        if elapsed_time < MIN_RESPONSE_TIME:
            remaining_time = MIN_RESPONSE_TIME - elapsed_time
            logger.info(f"[COLD_START] 等待 {remaining_time:.2f}s 以满足最小响应时间")
            await asyncio.sleep(remaining_time)

        # 生成成功消息
        message = (
            f"分析完成！基于你的学习特征，"
            f"数学预计{result.math_level}（{result.math_score:.1f}分），"
            f"阅读预计{result.reading_level}（{result.reading_score:.1f}分），"
            f"科学预计{result.science_level}（{result.science_score:.1f}分）。"
            f"已为你生成个性化学习方案！"
        )

        return _to_response(profile, result, message)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[COLD_START] 预测失败: {e}")
        raise HTTPException(status_code=500, detail=f"预测失败: {str(e)}")
