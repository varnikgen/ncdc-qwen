from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
import json

from app.database import get_db
from app.models import Account, AuditLog
from app.services.audit import log_action

router = APIRouter(prefix="/accounts", tags=["accounts"])

@router.get("/")
async def list_accounts(request: Request, db: Session = Depends(get_db)):
    accounts = db.query(Account).order_by(Account.name).all()
    
    return request.app.state.templates.TemplateResponse("accounts/list.html", {
        "request": request,
        "accounts": accounts
    })

@router.get("/new")
async def new_account(request: Request):
    return request.app.state.templates.TemplateResponse("accounts/edit.html", {
        "request": request,
        "account": None,
        "dss_keys": []
    })

@router.post("/")
async def create_account(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    
    account = Account(
        name=form.get("name"),
        sip_server=form.get("sip_server"),
        sip_port=int(form.get("sip_port", 5060)),
        transport=form.get("transport", "udp"),
        username=form.get("username"),
        password=form.get("password"),
        display_name=form.get("display_name"),
        dss_keys=json.loads(form.get("dss_keys", "[]"))
    )
    
    db.add(account)
    db.commit()
    db.refresh(account)
    
    log_action(db, "CREATE_ACCOUNT", "Account", account.id, "admin", f"Created account {account.name}")
    
    return {"status": "success", "message": f"Аккаунт {account.name} создан", "redirect": "/accounts"}

@router.get("/{account_id}/edit")
async def edit_account(request: Request, account_id: int, db: Session = Depends(get_db)):
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Аккаунт не найден")
    
    return request.app.state.templates.TemplateResponse("accounts/edit.html", {
        "request": request,
        "account": account,
        "dss_keys": account.dss_keys or []
    })

@router.post("/{account_id}/update")
async def update_account(request: Request, account_id: int, db: Session = Depends(get_db)):
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Аккаунт не найден")
    
    form = await request.form()
    
    account.name = form.get("name")
    account.sip_server = form.get("sip_server")
    account.sip_port = int(form.get("sip_port", 5060))
    account.transport = form.get("transport", "udp")
    account.username = form.get("username")
    account.password = form.get("password")
    account.display_name = form.get("display_name")
    account.dss_keys = json.loads(form.get("dss_keys", "[]"))
    
    db.commit()
    db.refresh(account)
    
    log_action(db, "UPDATE_ACCOUNT", "Account", account.id, "admin", f"Updated account {account.name}")
    
    return {"status": "success", "message": f"Аккаунт {account.name} обновлен", "redirect": "/accounts"}

@router.post("/{account_id}/delete")
async def delete_account(request: Request, account_id: int, db: Session = Depends(get_db)):
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Аккаунт не найден")
    
    account_name = account.name
    db.delete(account)
    db.commit()
    
    log_action(db, "DELETE_ACCOUNT", "Account", account_id, "admin", f"Deleted account {account_name}")
    
    return {"status": "success", "message": f"Аккаунт {account_name} удален", "redirect": "/accounts"}