//+------------------------------------------------------------------+
//| NEXUS VECTOR RETEST EA v1.00 — ORIGINAL FOREX / GOLD ROBOT        |
//| Strategy: breakout of prior structure + confirmed retest         |
//| Vector: breakout .25, retest .25, EMA .20, momentum .15, RVOL .15|
//| NO VWAP in this strategy. This is an EXPERIMENT, not a proven edge|
//| Demo by default: REAL trading requires explicit InpAllowReal=true|
//+------------------------------------------------------------------+
#property copyright "Nexus — Independent EA, 2026"
#property version   "1.00"
#property strict
#property description "Vector breakout/retest EA. M5/M15 preferred. Demo default. No guaranteed profits."

#include <Trade/Trade.mqh>

input group "01  ESTRATEGIA  |  Vetor matematico"
input int     InpRangeBars          = 24;    // Older candles used for price structure
input int     InpRetestMaxBars      = 8;     // Later CLOSED bars allowed to retest
input int     InpATRPeriod         = 14;
input int     InpEMAFast            = 21;
input int     InpEMASlow            = 55;
input int     InpMomentumBars       = 5;
input int     InpVolumeBars         = 20;
input double  InpBreakATR           = 0.08;  // Breakout minimum size / ATR
input double  InpTouchATR           = 0.18;  // Retest touch tolerance / ATR
input double  InpReclaimATR         = 0.04;  // Closed retest candle confirms side
input double  InpMinVectorScore     = 0.51;  // Weighted 0..1 score, NOT probability
input int     InpCooldownBars       = 8;     // Min time between executed entries
input bool    InpOnePerDirection    = true;  // No same-direction trade until opposite confirmed

input group "02  RISCO  |  Limitadores"
input bool    InpAutoTrade          = true;  // Auto orders DEMO only until real opt-in
input bool    InpAllowReal          = false; // MUST explicitly enable on REAL accounts
input double  InpRiskPercent       = 0.50;  // % account equity risk per position
input double  InpMaxDailyLossPct    = 2.00;  // Daily equity loss brake, no new trades
input int     InpMaxSpreadPoints    = 45;    // 0=disabled; broker SYMBOL_POINT units
input int     InpSlippagePoints     = 20;
input double  InpStopATRBuffer      = 0.14;
input double  InpMinStopATR         = 0.30;
input double  InpMaxStopATR         = 2.60;
input double  InpTP1R               = 1.00;
input double  InpTP2R               = 1.50;
input double  InpTP3R               = 2.00;
input ulong   InpMagic              = 26111251;
input int     InpHistoryDays        = 90;    // Statistics use actual closed deals only

input group "03  APRESENTACAO  |  Grafico e alertas"
input bool    InpShowPanel          = true;
input bool    InpShowTP_SL          = true;
input bool    InpSmallArrows        = true;
input bool    InpOutcomeLabels      = true;  // Actual points under arrows after full close
input bool    InpSound             = true;
input string  InpSoundFile          = "alert.wav";
input bool    InpPopup             = false;
input bool    InpPush              = false;

#define W_BREAK  0.25
#define W_RETEST 0.25
#define W_TREND  0.20
#define W_MOM    0.15
#define W_VOL    0.15

CTrade g_trade;
int g_atr=INVALID_HANDLE, g_fast=INVALID_HANDLE, g_slow=INVALID_HANDLE;
string g_prefix="";
datetime g_lastBar=0, g_breakTime=0, g_lastEntryBar=0, g_day=0;
int g_breakDir=0,g_breakAge=0,g_lastDir=0;
double g_breakLevel=0.0,g_breakQuality=0.0,g_dayStartEquity=0.0;
double g_entryVol=0.0,g_tp1=0.0,g_tp2=0.0,g_tp3=0.0,g_entry=0.0;
int g_tpStage=0;
datetime g_entryTime=0;
bool g_statsDirty=true;

struct TradeStats
  {
   int green;
   int red;
   int flat;
   double points;
   double money;
   double gains;
   double losses;
   double drawdown;
  };
TradeStats g_stats;

struct PositionRecord
  {
   long id;
   int direction;
   double inVolume;
   double inValue;
   double outVolume;
   double weightedPoints;
   double netMoney;
   datetime lastCloseTime;
   datetime entryTime;
  };

double Clip01(const double v) {return MathMax(0.0,MathMin(1.0,v));}

string Key(const string name)
  {
   return "NVR_"+IntegerToString((long)AccountInfoInteger(ACCOUNT_LOGIN))+"_"+
          _Symbol+"_"+IntegerToString((long)InpMagic)+"_"+name;
  }
void SaveStages()
  {
   GlobalVariableSet(Key("VOL"),g_entryVol);
   GlobalVariableSet(Key("TP1"),g_tp1);
   GlobalVariableSet(Key("TP2"),g_tp2);
   GlobalVariableSet(Key("TP3"),g_tp3);
   GlobalVariableSet(Key("STAGE"),(double)g_tpStage);
   GlobalVariableSet(Key("ENTRY"),g_entry);
   GlobalVariableSet(Key("ETIME"),(double)g_entryTime);
   GlobalVariableSet(Key("LAST_BAR"),(double)g_lastEntryBar);
  }
void LoadStages()
  {
   if(!GlobalVariableCheck(Key("VOL"))) return;
   g_entryVol=GlobalVariableGet(Key("VOL"));
   g_tp1=GlobalVariableGet(Key("TP1"));
   g_tp2=GlobalVariableGet(Key("TP2"));
   g_tp3=GlobalVariableGet(Key("TP3"));
   g_tpStage=(int)GlobalVariableGet(Key("STAGE"));
   g_entry=GlobalVariableGet(Key("ENTRY"));
   g_entryTime=(datetime)(long)GlobalVariableGet(Key("ETIME"));
   if(GlobalVariableCheck(Key("LAST_BAR")))
      g_lastEntryBar=(datetime)(long)GlobalVariableGet(Key("LAST_BAR"));
  }

// Never act on foreign positions; in NETTING, a foreign trade must not mix with ours.
bool OurPosition(ulong &ticket)
  {
   ticket=0;
   for(int i=PositionsTotal()-1;i>=0;i--)
     {
      const ulong candidate=PositionGetTicket(i);
      if(candidate==0) continue;
      if(PositionGetString(POSITION_SYMBOL)==_Symbol &&
         (ulong)PositionGetInteger(POSITION_MAGIC)==InpMagic)
        {ticket=candidate;return true;}
     }
   return false;
  }
bool AnySymbolPosition()
  {
   for(int i=PositionsTotal()-1;i>=0;i--)
     {
      if(PositionGetTicket(i)==0) continue;
      if(PositionGetString(POSITION_SYMBOL)==_Symbol) return true;
     }
   return false;
  }

int VolumeDigits()
  {
   double st=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP);
   for(int n=0;n<=8;n++)
     {if(MathAbs(st*MathPow(10.0,n)-MathRound(st*MathPow(10.0,n)))<1e-7) return n;}
   return 8;
  }
double FloorVolume(const double value)
  {
   const double mn=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN);
   const double mx=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MAX);
   const double step=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP);
   if(step<=0.0 || mn<=0.0 || value<mn-1e-8) return 0.0;
   const double capped=MathMin(value,mx);
   const double steps=MathFloor((capped+1e-10)/step);
   const double result=NormalizeDouble(steps*step,VolumeDigits());
   if(result<mn-1e-8) return 0.0;
   return result;
  }

// Dynamic risk, never increase to minimum lot if risk budget is insufficient.
double RiskVolume(const int direction,const double entry,const double sl)
  {
   double lossOneLot=0.0;
   ENUM_ORDER_TYPE side=(direction>0 ? ORDER_TYPE_BUY : ORDER_TYPE_SELL);
   if(!OrderCalcProfit(side,_Symbol,1.0,entry,sl,lossOneLot)) return 0.0;
   if(lossOneLot>=-0.000001) return 0.0;
   const double budget=AccountInfoDouble(ACCOUNT_EQUITY)*InpRiskPercent/100.0;
   const double lots=FloorVolume(budget/(-lossOneLot));
   if(lots<=0.0) return 0.0;
   double margin=0.0;
   if(!OrderCalcMargin(side,_Symbol,lots,entry,margin)) return 0.0;
   if(margin>0.75*AccountInfoDouble(ACCOUNT_MARGIN_FREE)) return 0.0;
   return lots;
  }

datetime DayStart(const datetime t)
  {
   MqlDateTime ts;TimeToStruct(t,ts);
   ts.hour=0;ts.min=0;ts.sec=0;
   return StructToTime(ts);
  }
void UpdateDay()
  {
   const datetime today=DayStart(TimeCurrent());
   if(today!=g_day)
     {
      g_day=today;
      g_dayStartEquity=AccountInfoDouble(ACCOUNT_EQUITY);
      GlobalVariableSet(Key("DAY"),(double)g_day);
      GlobalVariableSet(Key("START_EQ"),g_dayStartEquity);
     }
  }
string TradingBlock()
  {
   if(!InpAutoTrade) return "MODO SINAL (SEM ORDENS)";
   if(AccountInfoInteger(ACCOUNT_TRADE_MODE)==ACCOUNT_TRADE_MODE_REAL && !InpAllowReal)
      return "CONTA REAL BLOQUEADA";
   if(!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) ||
      !MQLInfoInteger(MQL_TRADE_ALLOWED) ||
      !AccountInfoInteger(ACCOUNT_TRADE_ALLOWED)) return "AUTOTRADING DESLIGADO";
   if(g_dayStartEquity>0.0 &&
      AccountInfoDouble(ACCOUNT_EQUITY)<g_dayStartEquity*(1.0-InpMaxDailyLossPct/100.0))
      return "TRAVA PERDA DIARIA";
   return "PRONTO";
  }

void ObjectText(const string id,const string label,const int x,const int y,
                const color colorText,const int size)
  {
   const string name=g_prefix+id;
   if(ObjectFind(0,name)<0)
     {
      if(!ObjectCreate(0,name,OBJ_LABEL,0,0,0)) return;
      ObjectSetInteger(0,name,OBJPROP_CORNER,CORNER_RIGHT_UPPER);
      ObjectSetInteger(0,name,OBJPROP_ANCHOR,ANCHOR_RIGHT_UPPER);
      ObjectSetInteger(0,name,OBJPROP_XDISTANCE,x);
      ObjectSetInteger(0,name,OBJPROP_YDISTANCE,y);
      ObjectSetString(0,name,OBJPROP_FONT,"Tahoma");
      ObjectSetInteger(0,name,OBJPROP_HIDDEN,true);
      ObjectSetInteger(0,name,OBJPROP_SELECTABLE,false);
     }
   ObjectSetString(0,name,OBJPROP_TEXT,label);
   ObjectSetInteger(0,name,OBJPROP_COLOR,colorText);
   ObjectSetInteger(0,name,OBJPROP_FONTSIZE,size);
  }
void DrawPanel()
  {
   if(!InpShowPanel) return;
   const string box=g_prefix+"BG";
   if(ObjectFind(0,box)<0)
     {
      if(ObjectCreate(0,box,OBJ_RECTANGLE_LABEL,0,0,0))
        {
         ObjectSetInteger(0,box,OBJPROP_CORNER,CORNER_RIGHT_UPPER);
         ObjectSetInteger(0,box,OBJPROP_XDISTANCE,8);
         ObjectSetInteger(0,box,OBJPROP_YDISTANCE,8);
         ObjectSetInteger(0,box,OBJPROP_XSIZE,257);
         ObjectSetInteger(0,box,OBJPROP_YSIZE,169);
         ObjectSetInteger(0,box,OBJPROP_BGCOLOR,C'14,22,35');
         ObjectSetInteger(0,box,OBJPROP_COLOR,C'39,71,96');
         ObjectSetInteger(0,box,OBJPROP_BORDER_TYPE,BORDER_FLAT);
         ObjectSetInteger(0,box,OBJPROP_BACK,false);
         ObjectSetInteger(0,box,OBJPROP_HIDDEN,true);
         ObjectSetInteger(0,box,OBJPROP_SELECTABLE,false);
        }
     }
   ObjectText("TITLE","NEXUS  /  VECTOR RETEST",20,17,C'100,206,244',10);
   ObjectText("RULE","ESTRUTURA  +  VETOR MATEMATICO",20,37,C'154,176,197',8);
   ObjectText("SCORE","PESOS  25 | 25 | 20 | 15 | 15",20,53,clrSilver,8);
   ObjectText("G","GREEN       "+IntegerToString(g_stats.green),20,74,clrLimeGreen,10);
   ObjectText("R","RED          "+IntegerToString(g_stats.red),20,91,clrTomato,10);
   ObjectText("POINTS","PONTOS       "+(g_stats.points>=0?"+":"")+DoubleToString(g_stats.points,1),20,110,
              (g_stats.points>=0?clrLimeGreen:clrTomato),10);
   ObjectText("USD","RESULTADO  "+DoubleToString(g_stats.money,2)+" "+AccountInfoString(ACCOUNT_CURRENCY),20,129,clrWhite,8);
   ObjectText("FOOT",TradingBlock()+" | RISCO "+DoubleToString(InpRiskPercent,2)+"%",20,153,C'173,188,203',7);
  }

void ChartLabel(const string suffix,const datetime timeBar,const double price,
                const string message,const color c,const int size)
  {
   const string name=g_prefix+suffix;
   if(ObjectFind(0,name)>=0) ObjectDelete(0,name);
   if(!ObjectCreate(0,name,OBJ_TEXT,0,timeBar,price)) return;
   ObjectSetString(0,name,OBJPROP_TEXT,message);
   ObjectSetString(0,name,OBJPROP_FONT,"Tahoma");
   ObjectSetInteger(0,name,OBJPROP_FONTSIZE,size);
   ObjectSetInteger(0,name,OBJPROP_COLOR,c);
   ObjectSetInteger(0,name,OBJPROP_SELECTABLE,false);
   ObjectSetInteger(0,name,OBJPROP_HIDDEN,true);
  }
void EntryArrow(const int direction,const datetime when,const double price)
  {
   const string id=g_prefix+"ARROW_"+IntegerToString((long)when);
   if(!ObjectCreate(0,id,OBJ_ARROW,0,when,price)) return;
   ObjectSetInteger(0,id,OBJPROP_ARROWCODE,(direction>0?233:234));
   ObjectSetInteger(0,id,OBJPROP_COLOR,(direction>0?clrLimeGreen:clrTomato));
   ObjectSetInteger(0,id,OBJPROP_WIDTH,(InpSmallArrows?1:2));
   ObjectSetInteger(0,id,OBJPROP_HIDDEN,true);
   ObjectSetInteger(0,id,OBJPROP_SELECTABLE,false);
  }
void Line(const string suffix,const datetime t0,const datetime t1,
          const double price,const color c,const ENUM_LINE_STYLE style)
  {
   const string id=g_prefix+"L_"+suffix;
   if(ObjectFind(0,id)<0)
     {
      if(!ObjectCreate(0,id,OBJ_TREND,0,t0,price,t1,price)) return;
      ObjectSetInteger(0,id,OBJPROP_RAY_LEFT,false);
      ObjectSetInteger(0,id,OBJPROP_RAY_RIGHT,false);
      ObjectSetInteger(0,id,OBJPROP_SELECTABLE,false);
      ObjectSetInteger(0,id,OBJPROP_HIDDEN,true);
     }
   ObjectMove(0,id,0,t0,price);
   ObjectMove(0,id,1,t1,price);
   ObjectSetInteger(0,id,OBJPROP_COLOR,c);
   ObjectSetInteger(0,id,OBJPROP_STYLE,style);
   ObjectSetInteger(0,id,OBJPROP_WIDTH,1);
  }
void ClearLevels()
  {
   for(int i=0;i<5;i++) ObjectDelete(0,g_prefix+"L_"+IntegerToString(i));
   for(int i=0;i<5;i++) ObjectDelete(0,g_prefix+"T_"+IntegerToString(i));
  }
void DrawLevels(const ulong ticket)
  {
   if(!InpShowTP_SL || ticket==0 || !PositionSelectByTicket(ticket)) return;
   const double sl=PositionGetDouble(POSITION_SL);
   datetime openTime=(datetime)PositionGetInteger(POSITION_TIME);
   datetime endTime=TimeCurrent()+(datetime)(12*PeriodSeconds(_Period));
   if(endTime<=openTime) endTime=openTime+3600;
   const double prices[5]={g_entry,sl,g_tp1,g_tp2,g_tp3};
   const color colors[5]={clrDeepSkyBlue,clrTomato,clrLimeGreen,clrMediumSeaGreen,clrGreen};
   const string names[5]={"ENTRADA","SL","TP1","TP2","TP3"};
   for(int i=0;i<5;i++)
     {
      if(prices[i]<=0.0) continue;
      const string suffix=IntegerToString(i);
      Line(suffix,openTime,endTime,prices[i],colors[i],(i<2?STYLE_DOT:STYLE_DASH));
      const string label=g_prefix+"T_"+suffix;
      if(ObjectFind(0,label)>=0) ObjectDelete(0,label);
      ChartLabel("T_"+suffix,endTime,prices[i],names[i]+" "+DoubleToString(prices[i],_Digits),colors[i],8);
     }
  }

// Actual-deal ledger. Groups entry/exit deals by broker position id.
// No simulated GREEN/RED; partial closes count only after final exit.
void RebuildStatistics()
  {
   g_stats.green=0;g_stats.red=0;g_stats.flat=0;
   g_stats.points=0;g_stats.money=0;g_stats.gains=0;g_stats.losses=0;
   g_stats.drawdown=0;
   PositionRecord groups[];
   const datetime from=TimeCurrent()-(datetime)(InpHistoryDays*86400);
   if(!HistorySelect(from,TimeCurrent())) return;
   const int deals=HistoryDealsTotal();
   const double point=SymbolInfoDouble(_Symbol,SYMBOL_POINT);
   // Pass 1: acquire entry fills of this magic only.
   for(int i=0;i<deals;i++)
     {
      const ulong deal=HistoryDealGetTicket(i);
      if(deal==0 || HistoryDealGetString(deal,DEAL_SYMBOL)!=_Symbol) continue;
      if((ulong)HistoryDealGetInteger(deal,DEAL_MAGIC)!=InpMagic) continue;
      const ENUM_DEAL_ENTRY entryType=(ENUM_DEAL_ENTRY)HistoryDealGetInteger(deal,DEAL_ENTRY);
      if(entryType!=DEAL_ENTRY_IN) continue;
      const long id=HistoryDealGetInteger(deal,DEAL_POSITION_ID);
      const ENUM_DEAL_TYPE side=(ENUM_DEAL_TYPE)HistoryDealGetInteger(deal,DEAL_TYPE);
      const int direction=(side==DEAL_TYPE_BUY?1:-1);
      int pos=-1;
      for(int j=0;j<ArraySize(groups);j++) if(groups[j].id==id){pos=j;break;}
      if(pos<0)
        {
         pos=ArraySize(groups);ArrayResize(groups,pos+1);
         groups[pos].id=id;groups[pos].direction=direction;
         groups[pos].inVolume=0;groups[pos].inValue=0;groups[pos].outVolume=0;
         groups[pos].weightedPoints=0;groups[pos].netMoney=0;groups[pos].lastCloseTime=0;
         groups[pos].entryTime=(datetime)HistoryDealGetInteger(deal,DEAL_TIME);
        }
      const double vol=HistoryDealGetDouble(deal,DEAL_VOLUME);
      groups[pos].inVolume+=vol;
      groups[pos].inValue+=HistoryDealGetDouble(deal,DEAL_PRICE)*vol;
     }
   // Pass 2: include all broker exits linked to those position IDs, even SL magic=0.
   for(int i=0;i<deals;i++)
     {
      const ulong deal=HistoryDealGetTicket(i);
      if(deal==0 || HistoryDealGetString(deal,DEAL_SYMBOL)!=_Symbol) continue;
      const long id=HistoryDealGetInteger(deal,DEAL_POSITION_ID);
      int j=-1;
      for(int k=0;k<ArraySize(groups);k++) if(groups[k].id==id){j=k;break;}
      if(j<0 || groups[j].inVolume<=0) continue;
      const ENUM_DEAL_ENTRY action=(ENUM_DEAL_ENTRY)HistoryDealGetInteger(deal,DEAL_ENTRY);
      const double commission=HistoryDealGetDouble(deal,DEAL_COMMISSION)+
                              HistoryDealGetDouble(deal,DEAL_SWAP)+HistoryDealGetDouble(deal,DEAL_FEE);
      groups[j].netMoney+=commission;
      if(action==DEAL_ENTRY_OUT || action==DEAL_ENTRY_OUT_BY || action==DEAL_ENTRY_INOUT)
        {
         const double volume=HistoryDealGetDouble(deal,DEAL_VOLUME);
         const double closePrice=HistoryDealGetDouble(deal,DEAL_PRICE);
         const double basis=groups[j].inValue/groups[j].inVolume;
         groups[j].outVolume+=volume;
         if(point>0.0)
            groups[j].weightedPoints+=(groups[j].direction*(closePrice-basis)/point)*volume/groups[j].inVolume;
         groups[j].netMoney+=HistoryDealGetDouble(deal,DEAL_PROFIT);
         const datetime when=(datetime)HistoryDealGetInteger(deal,DEAL_TIME);
         groups[j].lastCloseTime=when;
        }
     }
   // Complete groups only: don't mislabel floating P&L on partial positions.
   double equityPath=0.0,peak=0.0;
   for(int j=0;j<ArraySize(groups);j++)
     {
      if(groups[j].inVolume<=0 || groups[j].outVolume+1e-7<groups[j].inVolume) continue;
      const double net=groups[j].netMoney;
      g_stats.money+=net;
      g_stats.points+=groups[j].weightedPoints;
      if(net>0.000001){g_stats.green++;g_stats.gains+=net;}
      else if(net< -0.000001){g_stats.red++;g_stats.losses+=-net;}
      else g_stats.flat++;
      equityPath+=net;
      if(equityPath>peak) peak=equityPath;
      if(peak-equityPath>g_stats.drawdown)g_stats.drawdown=peak-equityPath;
      // Completed broker history only, no simulated winning labels.
      if(InpOutcomeLabels && groups[j].entryTime>TimeCurrent()-7*86400)
        {
         const string name=g_prefix+"RESULT_"+IntegerToString(groups[j].id);
         if(ObjectFind(0,name)<0)
           {
            const double openPrice=groups[j].inValue/groups[j].inVolume;
            const double offset=50*_Point;
            const double labelPrice=(groups[j].direction>0 ? openPrice-offset : openPrice+offset);
            const string pts=(groups[j].weightedPoints>=0?"+":"")+
                             DoubleToString(groups[j].weightedPoints,1)+" pts";
            ChartLabel("RESULT_"+IntegerToString(groups[j].id),groups[j].entryTime,
                       labelPrice,(net>=0?"+ ":"x ")+pts,
                       (net>=0?clrLimeGreen:clrTomato),8);
           }
        }
     }
   g_statsDirty=false;
  }

// Partial close using an OPPOSITE DEAL with position ticket. Works with
// both NETTING and HEDGING; never call CTrade.PositionClosePartial(netting).
bool ReducePosition(const ulong ticket,const double requestedVolume,const string reason)
  {
   if(!PositionSelectByTicket(ticket)) return false;
   const double currentVolume=PositionGetDouble(POSITION_VOLUME);
   const double vol=FloorVolume(MathMin(requestedVolume,currentVolume));
   if(vol<=0.0) return false;
   const ENUM_POSITION_TYPE posType=(ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
   MqlTick quote;if(!SymbolInfoTick(_Symbol,quote))return false;
   MqlTradeRequest req={};MqlTradeResult result={};
   req.action=TRADE_ACTION_DEAL;
   req.position=ticket;
   req.symbol=_Symbol;
   req.volume=vol;
   req.magic=InpMagic;
   req.type=(posType==POSITION_TYPE_BUY ? ORDER_TYPE_SELL : ORDER_TYPE_BUY);
   req.price=(posType==POSITION_TYPE_BUY ? quote.bid : quote.ask);
   req.deviation=InpSlippagePoints;
   req.comment=reason;
   const long allowed=(long)SymbolInfoInteger(_Symbol,SYMBOL_FILLING_MODE);
   if((allowed & SYMBOL_FILLING_IOC)==SYMBOL_FILLING_IOC)
      req.type_filling=ORDER_FILLING_IOC;
   else if((allowed & SYMBOL_FILLING_FOK)==SYMBOL_FILLING_FOK)
      req.type_filling=ORDER_FILLING_FOK;
   else req.type_filling=ORDER_FILLING_RETURN;
   if(!OrderSend(req,result))
     {
      Print("NEXUS reduction request failed, error=",GetLastError());return false;
     }
   if(result.retcode!=TRADE_RETCODE_DONE && result.retcode!=TRADE_RETCODE_DONE_PARTIAL)
     {
      Print("NEXUS reduction retcode=",result.retcode," ",result.comment);
      return false;
     }
   g_statsDirty=true;
   return true;
  }

void ManageOpenPosition()
  {
   ulong ticket=0;
   if(!OurPosition(ticket)) return;
   if(!PositionSelectByTicket(ticket))return;
   const double volume=PositionGetDouble(POSITION_VOLUME);
   const double minlot=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN);
   // If volume cannot be split into >= 3 broker-minimum parts,
   // TP1/TP2 remain visual only; broker TP3 closes 100%.
   if(g_entryVol<3.0*minlot-1e-8 || g_tp1<=0.0 || g_tp2<=0.0) return;
   MqlTick quote;if(!SymbolInfoTick(_Symbol,quote))return;
   const int dir=((ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY?1:-1);
   const double mark=(dir>0?quote.bid:quote.ask);
   const double part=FloorVolume(g_entryVol/3.0);
   if(part<=0.0)return;
   const double alreadyClosed=MathMax(0.0,g_entryVol-volume);
   const double step=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP);
   // Reconstruct stages from actual remaining broker volume. This survives
   // partial fills, restarts and delayed trade transactions.
   if(alreadyClosed+step/2.0>=2.0*part) g_tpStage=2;
   else if(alreadyClosed+step/2.0>=part) g_tpStage=1;
   if(g_tpStage==0 && dir*(mark-g_tp1)>=0.0)
     {
      const double needed=part-alreadyClosed;
      if(ReducePosition(ticket,needed,"NEXUS TP1"))SaveStages();
     }
   else if(g_tpStage==1 && dir*(mark-g_tp2)>=0.0)
     {
      const double needed=2.0*part-alreadyClosed;
      if(ReducePosition(ticket,MathMin(needed,volume-minlot),"NEXUS TP2"))
         SaveStages();
     }
  }

// A completed current candle is always shift 1; ranges use shift >=2.
void ExecuteSignal(const int dir,const double sl,const double score,const datetime confirmedTime);

void EvaluateNewCandle()
  {
   MqlRates r[];ArraySetAsSeries(r,true);
   const int n=MathMax(InpRangeBars,MathMax(InpVolumeBars,InpMomentumBars))+8;
   if(CopyRates(_Symbol,_Period,0,n,r)<n) return;
   double atr[],emaFast[],emaSlow[];
   if(CopyBuffer(g_atr,0,1,1,atr)!=1 ||
      CopyBuffer(g_fast,0,1,1,emaFast)!=1 ||
      CopyBuffer(g_slow,0,1,1,emaSlow)!=1) return;
   const double volatility=atr[0];
   if(volatility<=_Point) return;
   const datetime signalTime=r[1].time;
   double ceiling=-DBL_MAX,floor=DBL_MAX;
   for(int i=2;i<InpRangeBars+2;i++)
     {
      if(r[i].high>ceiling)ceiling=r[i].high;
      if(r[i].low<floor)floor=r[i].low;
     }
   const double priorRange=ceiling-floor;
   if(priorRange<0.35*volatility) return;
   int breakout=0;
   if(r[1].close>ceiling+InpBreakATR*volatility)breakout=1;
   else if(r[1].close<floor-InpBreakATR*volatility)breakout=-1;

   // Check pending setup BEFORE replacing it with a breakout from same candle.
   if(g_breakDir!=0)
     {
      g_breakAge++;
      if(g_breakAge>InpRetestMaxBars) g_breakDir=0;
      else if(signalTime>g_breakTime)
        {
         const int d=g_breakDir;
         const double tol=InpTouchATR*volatility;
         const bool touched=(d>0 ? r[1].low<=g_breakLevel+tol :
                                   r[1].high>=g_breakLevel-tol);
         const bool reclaimed=(d>0 ? r[1].close>=g_breakLevel+InpReclaimATR*volatility :
                                     r[1].close<=g_breakLevel-InpReclaimATR*volatility);
         const bool goodBody=(d*(r[1].close-r[1].open)>0.0);
         if(touched && reclaimed && goodBody)
           {
            const double impulse=Clip01((d*(r[1].close-g_breakLevel)/volatility)/0.55);
            const double ema=Clip01((d*(emaFast[0]-emaSlow[0])/volatility+0.07)/0.55);
            const double momentum=Clip01((d*(r[1].close-r[1+InpMomentumBars].close)/volatility)/1.40);
            double volumeAvg=0.0;
            for(int i=2;i<InpVolumeBars+2;i++)volumeAvg+=(double)r[i].tick_volume;
            volumeAvg/=InpVolumeBars;
            const double rvol=(volumeAvg>0.0 ? (double)r[1].tick_volume/volumeAvg : 0.0);
            const double relative=Clip01(rvol/1.80);
            // Normalized vector: weights sum exactly 1; score is NOT win rate.
            const double vectorScore=W_BREAK*g_breakQuality +
                                     W_RETEST*impulse + W_TREND*ema +
                                     W_MOM*momentum + W_VOL*relative;
            if(vectorScore>=InpMinVectorScore)
              {
               const double stop=(d>0 ? MathMin(r[1].low,g_breakLevel)-InpStopATRBuffer*volatility :
                                          MathMax(r[1].high,g_breakLevel)+InpStopATRBuffer*volatility);
               MqlTick quote;if(!SymbolInfoTick(_Symbol,quote))return;
               const double price=(d>0?quote.ask:quote.bid);
               const double risk=d*(price-stop);
               const int nowBars=iBarShift(_Symbol,_Period,g_lastEntryBar,true);
               if(risk>=InpMinStopATR*volatility && risk<=InpMaxStopATR*volatility &&
                  (g_lastEntryBar==0 || nowBars>=InpCooldownBars) &&
                  (!InpOnePerDirection || g_lastDir!=d) && !AnySymbolPosition())
                 {
                  g_breakDir=0;
                  ExecuteSignal(d,NormalizeDouble(stop,_Digits),vectorScore,signalTime);
                  return;
                 }
              }
           }
        }
     }
   // Cache a fresh breakout, permitting the retest only on a later candle.
   if(breakout!=0)
     {
      g_breakDir=breakout;
      g_breakLevel=(breakout>0?ceiling:floor);
      g_breakAge=0;
      g_breakTime=signalTime;
      g_breakQuality=Clip01((breakout*(r[1].close-g_breakLevel)/volatility)/0.70);
     }
  }

void ExecuteSignal(const int dir,const double sl,const double score,
                   const datetime confirmedTime)
  {
   const string blocked=TradingBlock();
   if(blocked!="PRONTO")
     {
      Print("NEXUS VECTOR signal, no order: ",blocked,
            " score=",DoubleToString(score,3));
      return;
     }
   MqlTick quote;if(!SymbolInfoTick(_Symbol,quote))return;
   if(InpMaxSpreadPoints>0 && (quote.ask-quote.bid)/_Point>InpMaxSpreadPoints)return;
   const double requestedPrice=(dir>0?quote.ask:quote.bid);
   const double lot=RiskVolume(dir,requestedPrice,sl);
   if(lot<=0.0)
     {
      Print("NEXUS: lot under min or margin insufficient. No risk increase.");return;
     }
   const double risk=dir*(requestedPrice-sl);
   const int brokerStopPts=(int)SymbolInfoInteger(_Symbol,SYMBOL_TRADE_STOPS_LEVEL);
   if(risk/_Point<=brokerStopPts+2 || risk<2*_Point) return;
   const double tp=NormalizeDouble(requestedPrice+dir*InpTP3R*risk,_Digits);
   const bool sent=(dir>0 ? g_trade.Buy(lot,_Symbol,0,sl,tp,"NEXUS_VECTOR_RETEST") :
                            g_trade.Sell(lot,_Symbol,0,sl,tp,"NEXUS_VECTOR_RETEST"));
   if(!sent || g_trade.ResultRetcode()!=TRADE_RETCODE_DONE)
     {
      Print("NEXUS: Order not filled. retcode=",g_trade.ResultRetcode(),
            " ",g_trade.ResultRetcodeDescription());return;
     }
   ulong ticket=0;if(!OurPosition(ticket)||!PositionSelectByTicket(ticket))
     {
      Print("NEXUS: fill reported; position not immediately found, inspect terminal.");return;
     }
   g_entry=PositionGetDouble(POSITION_PRICE_OPEN);
   g_entryVol=PositionGetDouble(POSITION_VOLUME);
   g_entryTime=(datetime)PositionGetInteger(POSITION_TIME);
   const double realRisk=dir*(g_entry-sl);
   if(realRisk<=0.0) {Print("NEXUS: invalid stop after slippage");return;}
   g_tp1=NormalizeDouble(g_entry+dir*InpTP1R*realRisk,_Digits);
   g_tp2=NormalizeDouble(g_entry+dir*InpTP2R*realRisk,_Digits);
   g_tp3=NormalizeDouble(g_entry+dir*InpTP3R*realRisk,_Digits);
   g_tpStage=0;SaveStages();
   if(!g_trade.PositionModify(ticket,sl,g_tp3) ||
      g_trade.ResultRetcode()!=TRADE_RETCODE_DONE)
     Print("NEXUS: TP3 modification not confirmed (initial broker TP remains).");
   g_lastEntryBar=iTime(_Symbol,_Period,0);
   g_lastDir=dir;GlobalVariableSet(Key("LAST_DIR"),(double)g_lastDir);SaveStages();
   const double arrowOffset=MathMax(2*_Point,0.16*realRisk);
   EntryArrow(dir,g_lastEntryBar,g_entry-dir*arrowOffset);
   DrawLevels(ticket);
   g_statsDirty=true;
   if(InpSound) PlaySound(InpSoundFile);
   const string msg="NEXUS VECTOR "+_Symbol+" "+EnumToString(_Period)+
                    (dir>0?" BUY ":" SELL ")+" SCORE "+DoubleToString(score,2);
   if(InpPopup)Alert(msg);
   if(InpPush)SendNotification(msg);
   Print(msg," entry=",g_entry," SL=",sl," TP3=",g_tp3);
  }

int OnInit()
  {
   if(InpRangeBars<5 || InpRetestMaxBars<1 || InpRetestMaxBars>50 ||
      InpATRPeriod<3 || InpEMAFast<2 || InpEMASlow<=InpEMAFast ||
      InpMomentumBars<1 || InpVolumeBars<3 ||
      InpRiskPercent<=0.0 || InpRiskPercent>3.0 ||
      InpMaxDailyLossPct<=0 || InpMaxDailyLossPct>10.0 ||
      InpMinVectorScore<0 || InpMinVectorScore>1 ||
      InpTP1R<=0 || InpTP2R<=InpTP1R || InpTP3R<=InpTP2R ||
      InpMinStopATR<=0 || InpMaxStopATR<=InpMinStopATR ||
      InpHistoryDays<1 || InpHistoryDays>3650 ||
      InpMagic==0) return INIT_PARAMETERS_INCORRECT;
   if(MathAbs(W_BREAK+W_RETEST+W_TREND+W_MOM+W_VOL-1.0)>0.000001)
      return INIT_FAILED;
   g_atr=iATR(_Symbol,_Period,InpATRPeriod);
   g_fast=iMA(_Symbol,_Period,InpEMAFast,0,MODE_EMA,PRICE_CLOSE);
   g_slow=iMA(_Symbol,_Period,InpEMASlow,0,MODE_EMA,PRICE_CLOSE);
   if(g_atr==INVALID_HANDLE || g_fast==INVALID_HANDLE || g_slow==INVALID_HANDLE)
      return INIT_FAILED;
   g_trade.SetExpertMagicNumber(InpMagic);
   g_trade.SetDeviationInPoints(InpSlippagePoints);
   g_trade.SetTypeFillingBySymbol(_Symbol);
   g_prefix="NVR_"+IntegerToString((long)ChartID())+"_";
   const datetime today=DayStart(TimeCurrent());
   if(GlobalVariableCheck(Key("DAY")) &&
      (datetime)(long)GlobalVariableGet(Key("DAY"))==today &&
      GlobalVariableCheck(Key("START_EQ")))
     {
      g_day=today;g_dayStartEquity=GlobalVariableGet(Key("START_EQ"));
     }
   else UpdateDay();
   LoadStages();
   if(GlobalVariableCheck(Key("LAST_DIR")))
      g_lastDir=(int)GlobalVariableGet(Key("LAST_DIR"));
   ulong startupTicket=0;
   if(OurPosition(startupTicket) && g_tp3<=0.0)
     {
      Print("NEXUS existing trade lacks saved TP state. Broker SL/TP still active; only server-side exit is relied on.");
     }
   g_lastBar=iTime(_Symbol,_Period,0); // Never process a past signal on attach.
   EventSetTimer(6);
   RebuildStatistics();
   DrawPanel();
   return INIT_SUCCEEDED;
  }
void OnDeinit(const int reason)
  {
   EventKillTimer();
   if(g_atr!=INVALID_HANDLE)IndicatorRelease(g_atr);
   if(g_fast!=INVALID_HANDLE)IndicatorRelease(g_fast);
   if(g_slow!=INVALID_HANDLE)IndicatorRelease(g_slow);
   ObjectsDeleteAll(0,g_prefix,0,-1);
  }
void OnTick()
  {
   UpdateDay();
   ulong ticket=0;
   if(OurPosition(ticket))
     {
      ManageOpenPosition();
     }
   else
     {
      if(g_entryVol>0.0){g_entryVol=0;g_tpStage=0;g_statsDirty=true;ClearLevels();}
     }
   const datetime currentBar=iTime(_Symbol,_Period,0);
   if(currentBar>0 && currentBar!=g_lastBar)
     {
      g_lastBar=currentBar;
      EvaluateNewCandle();
     }
  }
void OnTimer()
  {
   if(g_statsDirty)RebuildStatistics();
   ulong ticket=0;
   if(OurPosition(ticket))DrawLevels(ticket);
   DrawPanel();
   ChartRedraw(0);
  }
void OnTradeTransaction(const MqlTradeTransaction &trans,
                        const MqlTradeRequest &request,
                        const MqlTradeResult &result)
  {
   if(trans.type==TRADE_TRANSACTION_DEAL_ADD) g_statsDirty=true;
  }
//+------------------------------------------------------------------+
