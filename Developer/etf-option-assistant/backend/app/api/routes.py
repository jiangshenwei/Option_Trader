from fastapi import APIRouter, HTTPException

from app.adapters.eastmoney import get_adapter, get_data_status
from app.models.schemas import SettingsModel, TradeLeg, TradeLegToggle, TradeLegUpdate
from app.services.heatmap import build_heatmap, build_tquote
from app.services.settings_store import load_settings, save_settings
from app.services.trade_store import delete_trade, list_trades, replace_trades, toggle_trade, update_trade

router = APIRouter()


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/status")
def status():
    from app.adapters.live_market import fetch_option_chain_df, get_market_status
    from app.config import get_settings

    if get_settings().live_data and get_market_status()["chain_updated_at"] is None:
        fetch_option_chain_df(timeout=8.0, retries=0)
    return get_data_status()


@router.get("/home")
def home():
    return get_adapter().get_home_cards()


@router.get("/heatmap/{underlying}")
def heatmap(underlying: str):
    try:
        return build_heatmap(underlying)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/tquote/{underlying}")
def tquote(underlying: str, month_idx: int = 0):
    try:
        return build_tquote(underlying, month_idx)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/underlyings")
def underlyings():
    from app.adapters.eastmoney import UNDERLYINGS

    return [{"code": k, "name": v["name"]} for k, v in UNDERLYINGS.items()]


@router.get("/settings", response_model=SettingsModel)
def get_settings():
    return load_settings()


@router.put("/settings", response_model=SettingsModel)
def update_settings(body: SettingsModel):
    return save_settings(body)


@router.get("/trades", response_model=list[TradeLeg])
def get_trades():
    return list_trades()


@router.put("/trades", response_model=list[TradeLeg])
def put_trades(body: list[TradeLeg]):
    return replace_trades(body)


@router.post("/trades/toggle", response_model=list[TradeLeg])
def post_trade_toggle(body: TradeLegToggle):
    return toggle_trade(body)


@router.patch("/trades/{leg_key}", response_model=list[TradeLeg])
def patch_trade(leg_key: str, body: TradeLegUpdate):
    patch = body.model_dump(exclude_none=True)
    if not patch:
        return list_trades()
    return update_trade(leg_key, patch)


@router.get("/hv/{underlying}")
def hv_profile(underlying: str):
    from dataclasses import asdict

    from app.services.hv import get_hv_profile

    try:
        return asdict(get_hv_profile(underlying))
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/trades/{leg_key}", response_model=list[TradeLeg])
def remove_trade(leg_key: str):
    return delete_trade(leg_key)
