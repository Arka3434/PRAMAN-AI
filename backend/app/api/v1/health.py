from fastapi import APIRouter

router = APIRouter(tags=['health'])


@router.get('/health')
async def health() -> dict[str, str]:
    return {'status': 'ok', 'service': 'praman-backend'}


@router.get('/api/v1/health')
async def api_v1_health() -> dict[str, str]:
    return {'status': 'ok', 'service': 'praman-backend', 'api_version': 'v1'}
