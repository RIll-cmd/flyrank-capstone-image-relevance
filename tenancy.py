import hashlib,json,os,threading
from contextvars import ContextVar
from pathlib import Path
from starlette.responses import JSONResponse

current_tenant=ContextVar('tenant',default='local')

def database_path():
    base=Path(os.getenv('DATABASE_PATH','matching.db'))
    tenant=current_tenant.get()
    if tenant=='local': return str(base)
    digest=hashlib.sha256(tenant.encode()).hexdigest()[:24]
    return str(base.with_name(base.stem+'-tenant-'+digest+base.suffix))

class TenantMiddleware:
    def __init__(self,app):
        self.app=app;self.initialized=set();self.lock=threading.Lock()
    async def __call__(self,scope,receive,send):
        if scope['type']!='http':return await self.app(scope,receive,send)
        keys=json.loads(os.getenv('TENANT_API_KEYS','{}'))
        tenant='local'
        if keys and scope['path'] not in ('/health','/docs','/openapi.json','/docs/oauth2-redirect'):
            headers=dict(scope['headers']);key=headers.get(b'x-api-key',b'').decode()
            tenant=keys.get(key)
            if not tenant:return await JSONResponse({'detail':'Valid X-API-Key required'},status_code=401)(scope,receive,send)
        token=current_tenant.set(tenant)
        try:
            from store import initialize
            path=database_path()
            with self.lock:
                if path not in self.initialized:
                    initialize()
                    from store import connect
                    with connect() as db:
                        db.execute("UPDATE jobs SET status='interrupted' WHERE status IN ('queued','running')")
                        db.execute("UPDATE images SET status='pending' WHERE status='processing'")
                    self.initialized.add(path)
            await self.app(scope,receive,send)
        finally:current_tenant.reset(token)
