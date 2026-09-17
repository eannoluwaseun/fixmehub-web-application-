import os
from datetime import datetime, timedelta
from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import FileResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlalchemy import create_engine, String, Integer, Float, DateTime, Text, ForeignKey, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker, Session
import jwt
from passlib.context import CryptContext
BASE=Path(__file__).parent
URL=os.getenv('DATABASE_URL','sqlite:///./fixmehub.db').replace('postgres://','postgresql://',1)
engine=create_engine(URL,connect_args={'check_same_thread':False} if URL.startswith('sqlite') else {})
SessionLocal=sessionmaker(bind=engine)
pwd=CryptContext(schemes=['bcrypt'],deprecated='auto'); SECRET=os.getenv('JWT_SECRET','change-me')
app=FastAPI(title='FixMe Hub CRM'); auth=HTTPBearer(auto_error=False)
class Base(DeclarativeBase): pass
class User(Base):
 __tablename__='users'; id:Mapped[int]=mapped_column(primary_key=True); username:Mapped[str]=mapped_column(String(80),unique=True); password_hash:Mapped[str]=mapped_column(String(255))
class Customer(Base):
 __tablename__='customers'; id:Mapped[int]=mapped_column(primary_key=True); name:Mapped[str]=mapped_column(String(160)); phone:Mapped[str]=mapped_column(String(80),default=''); email:Mapped[str]=mapped_column(String(160),default=''); address:Mapped[str]=mapped_column(String(255),default=''); notes:Mapped[str]=mapped_column(Text,default=''); created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
class Job(Base):
 __tablename__='jobs'; id:Mapped[int]=mapped_column(primary_key=True); customer_id:Mapped[int]=mapped_column(ForeignKey('customers.id')); device:Mapped[str]=mapped_column(String(160)); repair_type:Mapped[str]=mapped_column(String(80),default='Hardware Repair'); description:Mapped[str]=mapped_column(Text,default=''); status:Mapped[str]=mapped_column(String(50),default='Open'); cost:Mapped[float]=mapped_column(Float,default=0); price:Mapped[float]=mapped_column(Float,default=0); created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
class Inventory(Base):
 __tablename__='inventory'; id:Mapped[int]=mapped_column(primary_key=True); part:Mapped[str]=mapped_column(String(160)); supplier:Mapped[str]=mapped_column(String(160),default=''); quantity:Mapped[int]=mapped_column(Integer,default=0); reorder_level:Mapped[int]=mapped_column(Integer,default=1); cost:Mapped[float]=mapped_column(Float,default=0); selling_price:Mapped[float]=mapped_column(Float,default=0)
class Sale(Base):
 __tablename__='sales'; id:Mapped[int]=mapped_column(primary_key=True); item:Mapped[str]=mapped_column(String(160)); quantity:Mapped[int]=mapped_column(Integer,default=1); cost:Mapped[float]=mapped_column(Float,default=0); price:Mapped[float]=mapped_column(Float,default=0); created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
class Expense(Base):
 __tablename__='expenses'; id:Mapped[int]=mapped_column(primary_key=True); category:Mapped[str]=mapped_column(String(100)); description:Mapped[str]=mapped_column(Text,default=''); amount:Mapped[float]=mapped_column(Float); created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
class Audit(Base):
 __tablename__='audit'; id:Mapped[int]=mapped_column(primary_key=True); username:Mapped[str]=mapped_column(String(80)); action:Mapped[str]=mapped_column(String(255)); created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
Base.metadata.create_all(engine)
db=SessionLocal(); admin=os.getenv('ADMIN_USER','admin')
if not db.query(User).filter_by(username=admin).first(): db.add(User(username=admin,password_hash=pwd.hash(os.getenv('ADMIN_PASSWORD','admin123')))); db.commit()
db.close()
def getdb():
 d=SessionLocal()
 try: yield d
 finally: d.close()
def user(c:HTTPAuthorizationCredentials=Depends(auth),db:Session=Depends(getdb)):
 if not c: raise HTTPException(401,'Login required')
 try: u=jwt.decode(c.credentials,SECRET,algorithms=['HS256'])
 except Exception: raise HTTPException(401,'Invalid token')
 x=db.query(User).filter_by(username=u.get('sub')).first()
 if not x: raise HTTPException(401,'Invalid user')
 return x
def log(db,u,msg): db.add(Audit(username=u.username,action=msg)); db.commit()
class Login(BaseModel): username:str; password:str
class CustomerIn(BaseModel): name:str; phone:str=''; email:str=''; address:str=''; notes:str=''
class JobIn(BaseModel): customer_id:int; device:str; repair_type:str='Hardware Repair'; description:str=''; status:str='Open'; cost:float=0; price:float=0
class InvIn(BaseModel): part:str; supplier:str=''; quantity:int=0; reorder_level:int=1; cost:float=0; selling_price:float=0
class SaleIn(BaseModel): item:str; quantity:int=1; cost:float=0; price:float=0
class ExpIn(BaseModel): category:str; description:str=''; amount:float
@app.get('/')
def home(): return FileResponse(BASE/'static'/'index.html')
@app.get('/health')
def health(): return {'ok':True}
@app.post('/api/login')
def login(x:Login,db:Session=Depends(getdb)):
 u=db.query(User).filter_by(username=x.username).first()
 if not u or not pwd.verify(x.password,u.password_hash): raise HTTPException(401,'Invalid username or password')
 t=jwt.encode({'sub':u.username,'exp':datetime.utcnow()+timedelta(hours=12)},SECRET,algorithm='HS256'); log(db,u,'Logged in'); return {'token':t,'username':u.username}
@app.get('/api/dashboard')
def dash(db:Session=Depends(getdb),u=Depends(user)):
 today=datetime.utcnow().date(); es=sum(x.amount for x in db.query(Expense).all() if x.created_at.date()==today); rp=db.query(Job).filter(func.date(Job.created_at)==today).count(); sp=sum((x.price-x.cost)*x.quantity for x in db.query(Sale).all() if x.created_at.date()==today); jp=sum(x.price-x.cost for x in db.query(Job).all() if x.created_at.date()==today); return {'repairs':rp,'expenses':es,'sales_profit':sp,'job_profit':jp,'net_profit':sp+jp-es}
@app.get('/api/customers')
def customers(db:Session=Depends(getdb),u=Depends(user)): return [{'id':x.id,'name':x.name,'phone':x.phone,'email':x.email,'address':x.address,'notes':x.notes} for x in db.query(Customer).order_by(Customer.id.desc())]
@app.post('/api/customers')
def addc(x:CustomerIn,db:Session=Depends(getdb),u=Depends(user)): o=Customer(**x.model_dump()); db.add(o); db.commit(); db.refresh(o); log(db,u,'Added customer '+o.name); return {'id':o.id}
@app.get('/api/jobs')
def jobs(db:Session=Depends(getdb),u=Depends(user)):
 return [{'id':x.id,'customer':db.get(Customer,x.customer_id).name if db.get(Customer,x.customer_id) else '','device':x.device,'repair_type':x.repair_type,'description':x.description,'status':x.status,'cost':x.cost,'price':x.price,'profit':x.price-x.cost} for x in db.query(Job).order_by(Job.id.desc())]
@app.post('/api/jobs')
def addj(x:JobIn,db:Session=Depends(getdb),u=Depends(user)): o=Job(**x.model_dump()); db.add(o); db.commit(); log(db,u,'Added repair job'); return {'id':o.id}
@app.get('/api/inventory')
def inv(db:Session=Depends(getdb),u=Depends(user)): return [{'id':x.id,'part':x.part,'supplier':x.supplier,'quantity':x.quantity,'reorder_level':x.reorder_level,'cost':x.cost,'selling_price':x.selling_price} for x in db.query(Inventory).order_by(Inventory.id.desc())]
@app.post('/api/inventory')
def addi(x:InvIn,db:Session=Depends(getdb),u=Depends(user)): o=Inventory(**x.model_dump()); db.add(o); db.commit(); log(db,u,'Added inventory '+o.part); return {'id':o.id}
@app.get('/api/sales')
def sales(db:Session=Depends(getdb),u=Depends(user)): return [{'id':x.id,'item':x.item,'quantity':x.quantity,'cost':x.cost,'price':x.price,'profit':(x.price-x.cost)*x.quantity,'created_at':x.created_at.isoformat()} for x in db.query(Sale).order_by(Sale.id.desc())]
@app.post('/api/sales')
def adds(x:SaleIn,db:Session=Depends(getdb),u=Depends(user)): o=Sale(**x.model_dump()); db.add(o); db.commit(); log(db,u,'Added sale '+o.item); return {'id':o.id}
@app.get('/api/expenses')
def exps(db:Session=Depends(getdb),u=Depends(user)): return [{'id':x.id,'category':x.category,'description':x.description,'amount':x.amount,'created_at':x.created_at.isoformat()} for x in db.query(Expense).order_by(Expense.id.desc())]
@app.post('/api/expenses')
def adde(x:ExpIn,db:Session=Depends(getdb),u=Depends(user)): o=Expense(**x.model_dump()); db.add(o); db.commit(); log(db,u,'Added expense '+o.category); return {'id':o.id}
@app.get('/api/audit')
def audit(db:Session=Depends(getdb),u=Depends(user)): return [{'id':x.id,'username':x.username,'action':x.action,'created_at':x.created_at.isoformat()} for x in db.query(Audit).order_by(Audit.id.desc()).limit(200)]
