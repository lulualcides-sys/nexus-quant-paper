//+------------------------------------------------------------------+
//| Nexus AlphaXAU Assistente v1.03 — Ollama DIRETO no painel          |
//| Implementação INDEPENDENTE baseada em funções visíveis no vídeo. |
//| IA aconselha APENAS; nenhuma resposta de IA envia ordens.        |
//| Requer confirmação dupla e negociação explicitamente habilitada. |
//+------------------------------------------------------------------+
#property strict
#property version   "1.03"
#property description "XAUUSD/GOLD | Ollama e registro estruturado por candle M15, SEM operacoes por IA."
#include <Trade/Trade.mqh>

input group "01 | Segurança"
input bool   InpTradingEnabled=false;   // padrão: análise, NÃO envia ordens
input bool   InpAllowReal=false;        // conta REAL BLOQUEADA por padrão
input double InpRiskPerTradePct=0.50;
input double InpMaxLots=0.50;
input double InpMaxSpreadUSD=1.50;      // diferença Ask-Bid no preço do ouro
input double InpMaxDailyDrawdownPct=2.0; // trava novas ordens; não garante limite de perda
input double InpMaxMarginPct=35.0;     // margem exigida <= 35% da margem livre
input int    InpConfirmSeconds=12;
input int    InpDeviationPoints=30;
input ulong  InpMagic=261115100;
input bool   InpBlockOtherPositions=true;

input group "02 | Plano técnico"
input int    InpLookback=25;
input int    InpATRPeriod=14;
input double InpStopATR=1.50;
input double InpTargetR=1.80;
input bool   InpOnlyAlignedTrades=true;
input bool   InpDrawTradeLevels=true;
input bool   InpShowExitDots=true;

input group "03 | Ollama JA INTEGRADO - SEM BRIDGE/PYTHON/API PAGA"
input bool   InpEnableIA=true;           // consulta apenas por clique
input string InpOllamaModel="llama3.2";  // instalado pelo instalador automatico
input int    InpOllamaTimeoutMs=90000;
input string InpDefaultPrompt="Analise scalp, tendencia, volume e risco. Se nao houver entrada, diga AGUARDAR.";
// URL local fixa por seguranca; nunca recebe endereco informado por IA ou mercado.
input group "04 | REGISTRO AUTOMATICO DE DECISOES (SEM ORDENS)"
input bool   InpRecordEveryM15=true;       // Automatico apenas no grafico XAUUSD M15
input double InpDecisionMinRR=1.00;        // rejeita sinais ruins
input double InpDecisionMaxRR=5.00;
input double InpDecisionMaxEntryDistanceATR=2.0;
input int    InpDecisionMaxTextChars=1200;
// Arquivos NDJSON sao gravados na pasta terminal COMMON\Files\NexusAlphaXAU
#define NQ_DECISION_PROMPT_VERSION "ALPHA_DECISION_2026_11_V1"
#define NQ_DECISION_MODEL_TEMP "0"
#define NQ_OLLAMA_URL "http://127.0.0.1:11434/api/chat"

CTrade g_trade;
int g_atr=INVALID_HANDLE,g_ema21=INVALID_HANDLE,g_ema55=INVALID_HANDLE;
string g_prefix="";
int g_dayKey=-1;
double g_dayStartEquity=0.0;
datetime g_lastChartBar=0;
// Journal causal; separate from manual trading logic.
datetime g_lastRecordAttemptBar=0;
int g_decisionCount=0;
string g_journalStatus="Registro IA aguardando M15 fechado.";

bool g_planReady=false;
int g_planBias=0;
double g_planSupport=0.,g_planResistance=0.,g_planATR=0.,g_planBuyLimit=0.,g_planSellLimit=0.;
string g_localAnalysis="Pressione ANALISAR para obter um plano técnico local.";
string g_aiText="OLLAMA integrado. Clique CONSULTAR IA LOCAL para analisar.";
string g_status="Somente análise | negociações DESLIGADAS";
string g_armedAction="";
datetime g_armExpiry=0;

color CLR_BG=C'24,26,31';
color CLR_PANEL=C'38,41,48';
color CLR_MUTED=C'161,169,182';
color CLR_BUY=C'51,161,103';
color CLR_SELL=C'218,89,86';
color CLR_GOLD=C'225,171,65';

string N(const string s){return g_prefix+s;}

bool ReadVal(const int h,const int shift,double &v)
  {
   double b[];
   if(h==INVALID_HANDLE || CopyBuffer(h,0,shift,1,b)!=1)return false;
   v=b[0];return MathIsValidNumber(v)&&v!=EMPTY_VALUE&&v>0.0;
  }

bool IsGoldSymbol()
  {
   string s=_Symbol;StringToUpper(s);
   return (StringFind(s,"XAUUSD")>=0 || StringFind(s,"GOLD")>=0);
  }

void RefreshRisk()
  {
   MqlDateTime tm;TimeToStruct(TimeCurrent(),tm);
   int key=tm.year*1000+tm.day_of_year;
   if(key!=g_dayKey){g_dayKey=key;g_dayStartEquity=AccountInfoDouble(ACCOUNT_EQUITY);}
  }

bool ValidTradeAccount()
  {
   if(!InpTradingEnabled)return false;
   if(AccountInfoInteger(ACCOUNT_TRADE_MODE)==ACCOUNT_TRADE_MODE_REAL&&!InpAllowReal)return false;
   if(!MQLInfoInteger(MQL_TESTER)&&!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED))return false;
   RefreshRisk();
   if(g_dayStartEquity>0.0 && InpMaxDailyDrawdownPct>0.0 &&
      AccountInfoDouble(ACCOUNT_EQUITY)<=g_dayStartEquity*(1.0-InpMaxDailyDrawdownPct/100.0))return false;
   return true;
  }

bool OwnPosition(const ulong ticket)
  {
   if(!PositionSelectByTicket(ticket))return false;
   return PositionGetString(POSITION_SYMBOL)==_Symbol &&
          (ulong)PositionGetInteger(POSITION_MAGIC)==InpMagic;
  }

bool OtherPositionOnSymbol()
  {
   if(!InpBlockOtherPositions)return false;
   for(int i=PositionsTotal()-1;i>=0;i--)
     {
      ulong tk=PositionGetTicket(i);
      if(tk<=0||!PositionSelectByTicket(tk))continue;
      if(PositionGetString(POSITION_SYMBOL)==_Symbol &&
        (ulong)PositionGetInteger(POSITION_MAGIC)!=InpMagic)return true;
     }
   return false;
  }

bool AlreadyHasOwnOrderOrPosition()
  {
   for(int i=PositionsTotal()-1;i>=0;i--)
     {
      ulong tk=PositionGetTicket(i);
      if(tk>0 && OwnPosition(tk))return true;
     }
   for(int i=OrdersTotal()-1;i>=0;i--)
     {
      ulong ticket=OrderGetTicket(i);
      if(ticket==0 || !OrderSelect(ticket))continue;
      if(OrderGetString(ORDER_SYMBOL)==_Symbol &&
         (ulong)OrderGetInteger(ORDER_MAGIC)==InpMagic)return true;
     }
   return false;
  }

bool GetTick(MqlTick &t)
  {
   if(!SymbolInfoTick(_Symbol,t))return false;
   return t.ask>0.0 && t.bid>0.0 && t.ask>=t.bid;
  }

int VolDecimals(double step)
  {
   int d=0;
   while(d<8 && MathAbs(step-MathRound(step))>0.000001){step*=10.0;d++;}
   return d;
  }

double RiskVolume(const ENUM_ORDER_TYPE side,const double price,const double stop)
  {
   const double mn=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN);
   const double mx=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MAX);
   const double step=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP);
   if(mn<=0 || mx<=0 || step<=0)return 0.;
   double oneLoss=0.0;
   if(!OrderCalcProfit(side,_Symbol,1.0,price,stop,oneLoss)||oneLoss>=0.0)return 0.0;
   const double budget=AccountInfoDouble(ACCOUNT_EQUITY)*InpRiskPerTradePct/100.0;
   if(budget<=0.0)return 0.0;
   double userLots=StringToDouble(ObjectGetString(0,N("LOT"),OBJPROP_TEXT));
   if(userLots<0.0)return 0.0;
   double intended=(userLots>0.0?userLots:budget/(-oneLoss));
   // Even a manually requested lot cannot exceed defined equity risk.
   intended=MathMin(intended,budget/(-oneLoss));
   intended=MathMin(intended,MathMin(InpMaxLots,mx));
   double rounded=MathFloor(intended/step+1.e-10)*step;
   if(rounded+1.e-8<mn)return 0.0; // never increase to min lot
   return NormalizeDouble(rounded,VolDecimals(step));
  }

double TickRound(const double x,const bool down)
  {
   const double step=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE);
   if(step<=0)return NormalizeDouble(x,_Digits);
   return NormalizeDouble((down?MathFloor(x/step+1e-9):MathCeil(x/step-1e-9))*step,_Digits);
  }

// Pivots require two bars fully CLOSED on both sides of the candidate.
// Approximate structures, NOT a proprietary Order Block/BOS indicator.
string FindConfirmedStructure(const MqlRates &b[],const int n,
                              const bool breakUp,const bool breakDown)
  {
   if(InpDrawTradeLevels)
     {ObjectDelete(0,N("LTA"));ObjectDelete(0,N("LTB"));
      ObjectDelete(0,N("ORDER_ZONE"));}
   int lowRecent=-1,lowOlder=-1,highRecent=-1,highOlder=-1;
   for(int i=3;i<InpLookback-2;i++)
     {
      bool pl=(b[i].low<b[i-1].low&&b[i].low<b[i-2].low&&
               b[i].low<b[i+1].low&&b[i].low<b[i+2].low);
      bool ph=(b[i].high>b[i-1].high&&b[i].high>b[i-2].high&&
               b[i].high>b[i+1].high&&b[i].high>b[i+2].high);
      if(pl){if(lowRecent<0)lowRecent=i;else if(lowOlder<0)lowOlder=i;}
      if(ph){if(highRecent<0)highRecent=i;else if(highOlder<0)highOlder=i;}
      if(lowOlder>=0&&highOlder>=0)break;
     }
   string info="";
   if(lowRecent>=0&&lowOlder>=0&&b[lowRecent].low>b[lowOlder].low)
     {
      info="LTA por fundos ascendentes. ";
      if(InpDrawTradeLevels)
        {
         string id=N("LTA");
         ObjectDelete(0,id);
         if(ObjectCreate(0,id,OBJ_TREND,0,b[lowOlder].time,b[lowOlder].low,
                          b[lowRecent].time,b[lowRecent].low))
           {ObjectSetInteger(0,id,OBJPROP_COLOR,clrLimeGreen);
            ObjectSetInteger(0,id,OBJPROP_RAY_RIGHT,true);
            ObjectSetInteger(0,id,OBJPROP_STYLE,STYLE_DOT);
            ObjectSetInteger(0,id,OBJPROP_SELECTABLE,false);}
        }
     }
   if(highRecent>=0&&highOlder>=0&&b[highRecent].high<b[highOlder].high)
     {
      info+="LTB por topos descendentes. ";
      if(InpDrawTradeLevels)
        {
         string id=N("LTB");ObjectDelete(0,id);
         if(ObjectCreate(0,id,OBJ_TREND,0,b[highOlder].time,b[highOlder].high,
                         b[highRecent].time,b[highRecent].high))
           {ObjectSetInteger(0,id,OBJPROP_COLOR,clrTomato);
            ObjectSetInteger(0,id,OBJPROP_RAY_RIGHT,true);
            ObjectSetInteger(0,id,OBJPROP_STYLE,STYLE_DOT);
            ObjectSetInteger(0,id,OBJPROP_SELECTABLE,false);}
        }
     }
   // Last opposite candle before CLOSED-bar breakout. Label as CANDIDATE,
   // since true order-block validation also needs displacement and retest.
   if(breakUp||breakDown)
     {
      for(int j=2;j<=MathMin(InpLookback,10);j++)
        {
         bool opposite=(breakUp?b[j].close<b[j].open:b[j].close>b[j].open);
         if(!opposite)continue;
         double top=b[j].high,bot=b[j].low;
         info+=(breakUp?"Zona de demanda candidata. ":"Zona de oferta candidata. ");
         if(InpDrawTradeLevels)
           {
            string id=N("ORDER_ZONE");ObjectDelete(0,id);
            datetime end=b[1].time+PeriodSeconds(_Period)*12;
            if(ObjectCreate(0,id,OBJ_RECTANGLE,0,b[j].time,top,end,bot))
              {ObjectSetInteger(0,id,OBJPROP_COLOR,
                                breakUp?C'29,88,62':C'101,44,46');
               ObjectSetInteger(0,id,OBJPROP_FILL,true);
               ObjectSetInteger(0,id,OBJPROP_BACK,true);
               ObjectSetInteger(0,id,OBJPROP_SELECTABLE,false);}
           }
         break;
        }
     }
   if(info=="")info="Sem LTA/LTB ou order block confirmados. ";
   return info;
  }

// Analysis is strictly based on completed candles [1..N], no future bars.
bool ComputePlan()
  {
   g_planReady=false;
   int n=MathMax(100,InpLookback+16);
   MqlRates b[];ArraySetAsSeries(b,true);
   if(CopyRates(_Symbol,_Period,0,n,b)<n){g_status="Sem histórico suficiente.";return false;}
   ArraySetAsSeries(b,true);
   double a=0.,e21=0.,e55=0.,e21prev=0.;
   if(!ReadVal(g_atr,1,a)||!ReadVal(g_ema21,1,e21)||
      !ReadVal(g_ema55,1,e55)||!ReadVal(g_ema21,6,e21prev))
      {g_status="Aguardando indicadores.";return false;}
   double hi=-DBL_MAX,lo=DBL_MAX,vol=0.;
   for(int j=2;j<2+InpLookback;j++)
     {hi=MathMax(hi,b[j].high);lo=MathMin(lo,b[j].low);
      vol+=(double)b[j].tick_volume;}
   g_planSupport=lo;g_planResistance=hi;g_planATR=a;
   const double close=b[1].close;
   const double relativeVolume=(vol>0.?(double)b[1].tick_volume/(vol/InpLookback):0.);
   const bool bullish=(e21>e55 && e21>e21prev && close>e21);
   const bool bearish=(e21<e55 && e21<e21prev && close<e21);
   g_planBias=(bullish?1:(bearish?-1:0));
   MqlTick t;if(!GetTick(t))return false;
   double minDist=(double)(SymbolInfoInteger(_Symbol,SYMBOL_TRADE_STOPS_LEVEL)+3)*_Point;
   g_planBuyLimit=TickRound(MathMin(t.ask-minDist,lo+0.20*a),true);
   g_planSellLimit=TickRound(MathMax(t.bid+minDist,hi-0.20*a),false);
   const bool breakUp=close>hi,breakDown=close<lo;
   string structure=FindConfirmedStructure(b,n,breakUp,breakDown);
   string regime=(g_planBias==1?"ALTA":g_planBias==-1?"BAIXA":"LATERAL/INCERTO");
   g_localAnalysis="Regime EMA21/55: "+regime+" | ATR "+DoubleToString(a,2)+
            " | Vol relativo "+DoubleToString(relativeVolume,2)+"x. "+
            "Suporte 25: "+DoubleToString(lo,_Digits)+"; resistencia 25: "+
            DoubleToString(hi,_Digits)+". "+
            (breakUp?"Fechamento acima da resistência.":breakDown?"Fechamento abaixo do suporte.":"Sem BOS confirmado neste candle.")+" "+
            structure+
            (g_planBias==0?"AGUARDAR: sem direcao clara.":
             "Entradas possiveis apenas após confirmação humana; níveis são aproximações.");
   g_planReady=true;
   if(InpDrawTradeLevels) DrawPlan();
   g_status="Análise local de candles FECHADOS atualizada.";
   return true;
  }

void ChartLine(const string key,const double price,const color clr,const ENUM_LINE_STYLE style)
  {
   const string id=N(key);
   if(ObjectFind(0,id)<0) ObjectCreate(0,id,OBJ_HLINE,0,0,price);
   ObjectSetDouble(0,id,OBJPROP_PRICE,price);
   ObjectSetInteger(0,id,OBJPROP_COLOR,clr);
   ObjectSetInteger(0,id,OBJPROP_STYLE,style);
   ObjectSetInteger(0,id,OBJPROP_WIDTH,1);
   ObjectSetInteger(0,id,OBJPROP_SELECTABLE,false);
   ObjectSetInteger(0,id,OBJPROP_HIDDEN,true);
  }

void DrawPlan()
  {
   if(!g_planReady)return;
   ChartLine("SUPPORT",g_planSupport,clrTeal,STYLE_DOT);
   ChartLine("RESISTANCE",g_planResistance,clrOrange,STYLE_DOT);
  }

void DrawTrade(const double entry,const double stop,const double target)
  {
   ChartLine("ENTRY",entry,clrWhite,STYLE_SOLID);
   ChartLine("SL",stop,CLR_SELL,STYLE_DASH);
   ChartLine("TP",target,clrLimeGreen,STYLE_DASH);
  }

void Rect(const string key,const int x,const int y,const int w,const int h,const color bg)
  {
   string id=N(key);
   if(!ObjectCreate(0,id,OBJ_RECTANGLE_LABEL,0,0,0))return;
   ObjectSetInteger(0,id,OBJPROP_CORNER,CORNER_LEFT_UPPER);
   ObjectSetInteger(0,id,OBJPROP_XDISTANCE,x);
   ObjectSetInteger(0,id,OBJPROP_YDISTANCE,y);
   ObjectSetInteger(0,id,OBJPROP_XSIZE,w);
   ObjectSetInteger(0,id,OBJPROP_YSIZE,h);
   ObjectSetInteger(0,id,OBJPROP_BGCOLOR,bg);
   ObjectSetInteger(0,id,OBJPROP_COLOR,bg);
   ObjectSetInteger(0,id,OBJPROP_BACK,false);
   ObjectSetInteger(0,id,OBJPROP_SELECTABLE,false);
   ObjectSetInteger(0,id,OBJPROP_HIDDEN,true);
  }

void Label(const string key,const int x,const int y,const string txt,
           const color fg=clrWhite,const int size=9)
  {
   string id=N(key);
   if(ObjectFind(0,id)<0)ObjectCreate(0,id,OBJ_LABEL,0,0,0);
   ObjectSetInteger(0,id,OBJPROP_CORNER,CORNER_LEFT_UPPER);
   ObjectSetInteger(0,id,OBJPROP_XDISTANCE,x);
   ObjectSetInteger(0,id,OBJPROP_YDISTANCE,y);
   ObjectSetInteger(0,id,OBJPROP_COLOR,fg);
   ObjectSetInteger(0,id,OBJPROP_FONTSIZE,size);
   ObjectSetInteger(0,id,OBJPROP_SELECTABLE,false);
   ObjectSetInteger(0,id,OBJPROP_HIDDEN,true);
   ObjectSetString(0,id,OBJPROP_FONT,"Arial");
   ObjectSetString(0,id,OBJPROP_TEXT,txt);
  }

void Button(const string key,const string txt,const int x,const int y,
            const int w,const int h,const color bg)
  {
   string id=N(key);
   if(!ObjectCreate(0,id,OBJ_BUTTON,0,0,0))return;
   ObjectSetInteger(0,id,OBJPROP_CORNER,CORNER_LEFT_UPPER);
   ObjectSetInteger(0,id,OBJPROP_XDISTANCE,x);
   ObjectSetInteger(0,id,OBJPROP_YDISTANCE,y);
   ObjectSetInteger(0,id,OBJPROP_XSIZE,w);
   ObjectSetInteger(0,id,OBJPROP_YSIZE,h);
   ObjectSetInteger(0,id,OBJPROP_BGCOLOR,bg);
   ObjectSetInteger(0,id,OBJPROP_COLOR,clrWhite);
   ObjectSetInteger(0,id,OBJPROP_FONTSIZE,9);
   ObjectSetInteger(0,id,OBJPROP_BORDER_COLOR,C'70,76,83');
   ObjectSetInteger(0,id,OBJPROP_SELECTABLE,false);
   ObjectSetInteger(0,id,OBJPROP_HIDDEN,true);
   ObjectSetString(0,id,OBJPROP_TEXT,txt);
  }

void Edit(const string key,const string txt,const int x,const int y,
          const int w,const int h)
  {
   string id=N(key);
   if(!ObjectCreate(0,id,OBJ_EDIT,0,0,0))return;
   ObjectSetInteger(0,id,OBJPROP_CORNER,CORNER_LEFT_UPPER);
   ObjectSetInteger(0,id,OBJPROP_XDISTANCE,x);
   ObjectSetInteger(0,id,OBJPROP_YDISTANCE,y);
   ObjectSetInteger(0,id,OBJPROP_XSIZE,w);
   ObjectSetInteger(0,id,OBJPROP_YSIZE,h);
   ObjectSetInteger(0,id,OBJPROP_COLOR,clrWhite);
   ObjectSetInteger(0,id,OBJPROP_BGCOLOR,C'52,56,64');
   ObjectSetInteger(0,id,OBJPROP_BORDER_COLOR,C'97,101,110');
   ObjectSetInteger(0,id,OBJPROP_FONTSIZE,9);
   ObjectSetInteger(0,id,OBJPROP_ALIGN,ALIGN_LEFT);
   ObjectSetInteger(0,id,OBJPROP_READONLY,false);
   ObjectSetInteger(0,id,OBJPROP_SELECTABLE,false);
   ObjectSetInteger(0,id,OBJPROP_HIDDEN,true);
   ObjectSetString(0,id,OBJPROP_TEXT,txt);
  }

void Wrapped(const string base,const string text,const int x,const int y,
             const int maxLines,const int limit,const color ink)
  {
   // OBJ_LABEL is single-line. Wrap by words without relying on HTML/OBJ_EDIT.
   string rest=text;
   StringReplace(rest,"\r"," ");StringReplace(rest,"\n"," ");
   for(int i=0;i<maxLines;i++)
     {
      string chunk="";
      while(StringLen(rest)>0)
        {
         int sep=StringFind(rest," ");
         string word=(sep<0?rest:StringSubstr(rest,0,sep));
         string candidate=(StringLen(chunk)==0?word:chunk+" "+word);
         if(StringLen(candidate)>limit && StringLen(chunk)>0)break;
         if(StringLen(candidate)>limit)
           {chunk=StringSubstr(word,0,limit);rest=StringSubstr(word,limit)+" "+StringSubstr(rest,sep<0?StringLen(rest):sep+1);break;}
         chunk=candidate;
         rest=(sep<0?"":StringSubstr(rest,sep+1));
         StringTrimLeft(rest);
         if(StringLen(chunk)>=limit)break;
        }
      Label(base+IntegerToString(i),x,y+i*15,chunk,ink,8);
     }
  }

void BuildUI()
  {
   Rect("BG",8,22,416,759,CLR_BG);
   Rect("HEADER",14,28,403,53,CLR_PANEL);
   Label("TITLE",24,35,"NEXUS ALPHA XAU  |  OLLAMA LOCAL",clrWhite,12);
   Label("MODE",24,60,"ANALISE | Trading OFF | GOLD",CLR_GOLD,9);
   Label("PROMPT_TITLE",20,88,"PROMPT (uma linha; edite antes de enviar)",CLR_MUTED,8);
   Edit("PROMPT",InpDefaultPrompt,20,109,388,31);
   Button("ANALYZE","ANALISAR GRAFICO",20,146,188,30,CLR_GOLD);
   Button("ASK_AI","CONSULTAR OLLAMA",219,146,189,30,C'83,74,149');
   Label("LOCAL_HEADER",22,184,"ANALISE LOCAL - precos e volume",CLR_GOLD,9);
   Rect("LOCALBG",20,203,389,91,C'33,36,43');
   Label("AI_HEADER",22,303,"OLLAMA LOCAL - analise consultiva",CLR_MUTED,9);
   Rect("AIBG",20,323,389,118,C'33,36,43');
   Label("INPUTS_TITLE",22,450,"LOTES  (0=risco automatico)    PRECO PENDENTE",CLR_MUTED,8);
   Edit("LOT","0",20,468,154,27);
   Edit("PRICE","0",202,468,206,27);
   Button("BUY","COMPRA MERCADO",20,503,188,30,CLR_BUY);
   Button("SELL","VENDA MERCADO",220,503,188,30,CLR_SELL);
   Button("PBUY","COMPRA PENDENTE",20,539,188,29,C'56,115,88');
   Button("PSELL","VENDA PENDENTE",220,539,188,29,C'125,70,70');
   Button("CANCEL","CANCELAR ORDENS",20,574,188,28,C'87,90,99');
   Button("REVERSE","REVERTER",220,574,188,28,C'87,90,99');
   Button("FLAT","ZERAR POSICOES",20,608,188,29,C'149,54,53');
   Button("ALL","CANCELAR + ZERAR",220,608,188,29,C'149,54,53');
   Rect("RESULTBG",20,648,388,69,CLR_PANEL);
   Label("OPEN",27,655,"Lotes: 0.00  |  Aberto: 0.00 USD",clrWhite,9);
   Label("DAY",27,680,"Realizado no dia: 0.00 USD",clrWhite,9);
   Label("STATUS",20,725,g_status,CLR_MUTED,8);
   Label("NOTE",20,750,"IA NAO ENVIA ORDENS | Registro M15 "+(InpRecordEveryM15?"ON":"OFF"),CLR_GOLD,8);
   Wrapped("L",g_localAnalysis,27,208,5,53,clrWhite);
   Wrapped("A",g_aiText,27,327,7,54,CLR_MUTED);
   ChartRedraw();
  }

void RefreshTexts()
  {
   string mode="ANALISE | "+(InpTradingEnabled?"TRADING HABILITADO":"TRADING DESLIGADO")+
      " | "+_Symbol+" "+EnumToString(_Period);
   Label("MODE",24,60,mode,(InpTradingEnabled?clrOrange:CLR_GOLD),9);
   Wrapped("L",g_localAnalysis,27,208,5,53,clrWhite);
   Wrapped("A",g_aiText,27,327,7,54,CLR_MUTED);
   Label("STATUS",20,725,StringSubstr(g_status,0,65),CLR_MUTED,8);
  }

void RefreshPnL()
  {
   double lots=0.,openResult=0.,dayResult=0.;
   for(int i=PositionsTotal()-1;i>=0;i--)
     {
      ulong tk=PositionGetTicket(i);
      if(tk==0||!OwnPosition(tk))continue;
      lots+=PositionGetDouble(POSITION_VOLUME);
      openResult+=PositionGetDouble(POSITION_PROFIT)+PositionGetDouble(POSITION_SWAP);
     }
   MqlDateTime dt;TimeToStruct(TimeCurrent(),dt);
   dt.hour=0;dt.min=0;dt.sec=0;
   datetime dayStart=StructToTime(dt);
   if(HistorySelect(dayStart,TimeCurrent()))
     {
      for(int i=0;i<HistoryDealsTotal();i++)
        {
         ulong id=HistoryDealGetTicket(i);
         if(id==0||HistoryDealGetString(id,DEAL_SYMBOL)!=_Symbol)continue;
         if((ulong)HistoryDealGetInteger(id,DEAL_MAGIC)!=InpMagic)continue;
         dayResult+=HistoryDealGetDouble(id,DEAL_PROFIT)+
                    HistoryDealGetDouble(id,DEAL_COMMISSION)+
                    HistoryDealGetDouble(id,DEAL_SWAP);
        }
     }
   string currency=AccountInfoString(ACCOUNT_CURRENCY);
   Label("OPEN",27,655,"Lotes: "+DoubleToString(lots,2)+
          " | Aberto: "+DoubleToString(openResult,2)+" "+currency,(openResult>=0?clrLimeGreen:clrTomato),9);
   Label("DAY",27,680,"Realizado no dia: "+DoubleToString(dayResult,2)+" "+currency,
        (dayResult>=0?clrLimeGreen:clrTomato),9);
  }

string JsonEscape(string s)
  {
   StringReplace(s,"\\","\\\\");
   StringReplace(s,"\"","\\\"");
   StringReplace(s,"\r"," ");
   StringReplace(s,"\n"," ");
   StringReplace(s,"\t"," ");
   return s;
  }

string BarsJSON()
  {
   MqlRates b[];ArraySetAsSeries(b,true);
   if(CopyRates(_Symbol,_Period,0,49,b)<49)return "";
   ArraySetAsSeries(b,true);
   string json="[";
   // Chronological order; exclude unfinished bar[0].
   for(int i=48;i>=1;i--)
     {
      if(i<48)json+=",";
      json+="{\"t\":"+IntegerToString((long)b[i].time)+
          ",\"o\":"+DoubleToString(b[i].open,_Digits)+
          ",\"h\":"+DoubleToString(b[i].high,_Digits)+
          ",\"l\":"+DoubleToString(b[i].low,_Digits)+
          ",\"c\":"+DoubleToString(b[i].close,_Digits)+
          ",\"v\":"+IntegerToString((long)b[i].tick_volume)+"}";
     }
   return json+"]";
  }

// Read a JSON quoted string from Ollama response (RFC 8259 subset),
// including escaped quotes and \\u Unicode code units. Do not execute it.
int HexValue(const ushort c)
  {
   if(c>=48 && c<=57)return (int)c-48;
   if(c>=65 && c<=70)return (int)c-65+10;
   if(c>=97 && c<=102)return (int)c-97+10;
   return -1;
  }

bool OllamaExtractText(const string response,string &out)
  {
   out="";
   int from=StringFind(response,"\"message\"");
   if(from<0)return false;
   int key=StringFind(response,"\"content\"",from+9);
   if(key<0)return false;
   int colon=StringFind(response,":",key+9);
   if(colon<0)return false;
   int n=StringLen(response),pos=colon+1;
   while(pos<n)
     {
      ushort c=StringGetCharacter(response,pos);
      if(c==32 || c==9 || c==10 || c==13){pos++;continue;}
      break;
     }
   if(pos>=n || StringGetCharacter(response,pos)!=34)return false;
   pos++;
   while(pos<n && StringLen(out)<3000)
     {
      ushort c=StringGetCharacter(response,pos++);
      if(c==34)return StringLen(out)>0;
      if(c!=92)
        {out+=ShortToString(c);continue;}
      if(pos>=n)return false;
      ushort esc=StringGetCharacter(response,pos++);
      if(esc==34 || esc==92 || esc==47)out+=ShortToString(esc);
      else if(esc==110)out+=" ";   // escaped newline
      else if(esc==114 || esc==116 || esc==98 || esc==102)out+=" ";
      else if(esc==117)
        {
         if(pos+4>n)return false;
         int val=0;
         for(int j=0;j<4;j++)
           {
            int h=HexValue(StringGetCharacter(response,pos++));
            if(h<0)return false;
            val=val*16+h;
           }
         if(val==0) return false;
         out+=ShortToString((ushort)val);
        }
      else return false;
     }
   return false;
  }

bool ValidOllamaModel(const string model)
  {
   int n=StringLen(model);
   if(n<1 || n>90)return false;
   for(int i=0;i<n;i++)
     {
      ushort c=StringGetCharacter(model,i);
      if((c>=48&&c<=57)||(c>=65&&c<=90)||(c>=97&&c<=122) ||
         c==46 || c==95 || c==45 || c==58)continue;
      return false;
     }
   return true;
  }

void AskIA()
  {
   if(!InpEnableIA)
     {g_status="Ollama desligado nas configuracoes do EA.";return;}
   if(MQLInfoInteger(MQL_TESTER))
     {g_status="MT5 nao permite WebRequest no Strategy Tester.";return;}
   if(!ValidOllamaModel(InpOllamaModel))
     {g_status="Modelo Ollama invalido. Use llama3.2, por exemplo.";return;}
   string bars=BarsJSON();
   if(StringLen(bars)<10)
     {g_status="Faltam 48 candles completos para consultar o Ollama.";return;}
   string prompt=ObjectGetString(0,N("PROMPT"),OBJPROP_TEXT);
   if(StringLen(prompt)>600)prompt=StringSubstr(prompt,0,600);
   // DIRECT communication MT5 -> Ollama 11434: no Python, no proxy,
   // no cloud API key and no local token shared with another process.
   string system="Voce e um ANALISTA TECNICO, nao um operador automatico. "+
                 "Analise SOMENTE os 48 candles fechados de GOLD/XAUUSD recebidos. "
                 "Responda em portugues BR de forma concisa: tendencia, suporte, "+
                 "resistencia, possivel cenario e risco. Nunca invente noticias, "+
                 "precos externos, resultados ou lucro. Se nao houver evidencias, "+
                 "diga AGUARDAR. Nao produza comandos de trading.";
   string question="Ativo "+_Symbol+" / "+EnumToString(_Period)+
                   ". Pedido: "+prompt+". Candles OHLCV fechados, "+
                   "do mais antigo para o recente: "+bars;
   string body="{\"model\":\""+JsonEscape(InpOllamaModel)+"\",\"stream\":false,"+
               "\"messages\":[{\"role\":\"system\",\"content\":\""+
               JsonEscape(system)+"\"},{\"role\":\"user\",\"content\":\""+
               JsonEscape(question)+"\"}],\"options\":{\"temperature\":0.2,"+
               "\"num_predict\":240}}";
   char payload[];
   StringToCharArray(body,payload,0,WHOLE_ARRAY,CP_UTF8);
   if(ArraySize(payload)>0)ArrayResize(payload,ArraySize(payload)-1);
   char result[];string resHeaders="";
   const string reqHeaders="Content-Type: application/json\r\n";
   ResetLastError();
   int http=WebRequest("POST",NQ_OLLAMA_URL,reqHeaders,InpOllamaTimeoutMs,
                       payload,result,resHeaders);
   if(http!=200)
     {
      const int lastError=GetLastError();
      g_aiText="Falha no Ollama. Instale/abra via INSTALAR_TUDO e libere "+
               "http://127.0.0.1:11434 no WebRequest do MT5.";
      g_status=(http<0 ? "WebRequest erro MT5 "+IntegerToString(lastError) :
                            "Ollama retornou HTTP "+IntegerToString(http));
      return;
     }
   string text="";
   const string response=CharArrayToString(result,0,ArraySize(result),CP_UTF8);
   if(!OllamaExtractText(response,text))
     {
      g_aiText="Resposta inesperada do Ollama. Confira modelo local.";
      g_status="Nao foi possivel ler message.content. Nenhuma ordem enviada.";
      return;
     }
   g_aiText=text;
   Print("NEXUS OLLAMA (somente analise): ",text);
   if(StringLen(g_aiText)>350)g_aiText=StringSubstr(g_aiText,0,345)+" ... (completo no Diario)";
   g_status="Ollama analisou candles fechados. IA nao executa ordens.";
  }


// Storage is NDJSON, append-only, common across MT5 terminal data directories.
// No orders are sent from this journal; the returned message is treated as DATA.
string JournalRoot(){return "NexusAlphaXAU\\";}
string JournalFile(const string label)
  {
   string symbol=_Symbol;
   StringReplace(symbol,"/","_");StringReplace(symbol,"\\","_");
   return JournalRoot()+label+"_"+IntegerToString((long)AccountInfoInteger(ACCOUNT_LOGIN))+
          "_"+symbol+"_M15.ndjson";
  }

bool AppendNDJSON(const string name,const string line)
  {
   ResetLastError();
   int h=FileOpen(JournalFile(name),FILE_TXT|FILE_READ|FILE_WRITE|FILE_COMMON|
                  FILE_SHARE_READ|FILE_ANSI,0,CP_UTF8);
   if(h==INVALID_HANDLE)
     {Print("ALPHA JOURNAL: Falha FileOpen ",name," erro=",GetLastError());return false;}
   FileSeek(h,0,SEEK_END);
   FileWriteString(h,line+"\r\n");
   FileFlush(h);FileClose(h);
   return true;
  }

// A flat, exact-key JSON value extractor; rejects invalid types and other keys.
// Data returned by Ollama are never interpreted as MQL5 instructions.
bool FlatJSONString(const string source,const string key,string &out)
  {
   out="";
   const int start=StringFind(source,"\""+key+"\"");
   if(start<0)return false;
   const int colon=StringFind(source,":",start+StringLen(key)+2);
   if(colon<0)return false;
   int i=colon+1,n=StringLen(source);
   while(i<n)
     {
      ushort c=StringGetCharacter(source,i);
      if(c==32||c==9||c==13||c==10){i++;continue;}
      break;
     }
   if(i>=n||StringGetCharacter(source,i)!=34)return false;
   i++;
   while(i<n && StringLen(out)<500)
     {
      ushort c=StringGetCharacter(source,i++);
      if(c==34)return true;
      if(c==92)
        {
         if(i>=n)return false;
         ushort esc=StringGetCharacter(source,i++);
         if(esc==34||esc==92||esc==47)out+=ShortToString(esc);
         else if(esc==110||esc==116||esc==114)out+=" ";
         else if(esc==117)
           {
            if(i+4>n)return false;
            int x=0;
            for(int m=0;m<4;m++)
              {
               int v=HexValue(StringGetCharacter(source,i++));
               if(v<0)return false;
               x=x*16+v;
              }
            if(x==0)return false;
            out+=ShortToString((ushort)x);
           }
         else return false;
        }
      else
        {
         if(c<32)return false;
         out+=ShortToString(c);
        }
     }
   return false;
  }

bool FlatJSONNumber(const string source,const string key,double &out)
  {
   out=0.0;
   const int start=StringFind(source,"\""+key+"\"");
   if(start<0)return false;
   int pos=StringFind(source,":",start+StringLen(key)+2);
   if(pos<0)return false;
   pos++;
   while(pos<StringLen(source)&&StringGetCharacter(source,pos)==32)pos++;
   // Only unsigned/negative ordinary decimal notations. No quoted numbers,
   // NaN, Infinity, null or ambiguous formats are accepted.
   string token="";
   while(pos<StringLen(source)&&StringLen(token)<32)
     {
      ushort c=StringGetCharacter(source,pos);
      if((c>=48&&c<=57)||c==46||c==45||c==43||c==101||c==69)
        {token+=ShortToString(c);pos++;}
      else break;
     }
   if(StringLen(token)==0)return false;
   int digits=0;
   for(int j=0;j<StringLen(token);j++)
     {ushort c=StringGetCharacter(token,j);if(c>=48&&c<=57)digits++;}
   if(digits==0)return false;
   while(pos<StringLen(source)&&StringGetCharacter(source,pos)==32)pos++;
   if(pos>=StringLen(source))return false;
   const ushort delim=StringGetCharacter(source,pos);
   if(delim!=44 && delim!=125)return false;
   out=StringToDouble(token);
   return MathIsValidNumber(out) && MathAbs(out)<1.0e8;
  }

bool DecodePlan(const string content,const double close,const double atr,
                string &direction,double &entry,double &stop,double &target,string &reason)
  {
   direction="WAIT";entry=0.;stop=0.;target=0.;reason="";
   string action="";
   if(!FlatJSONString(content,"direction",action))return false;
   if(action!="WAIT"&&action!="BUY"&&action!="SELL")return false;
   if(!FlatJSONString(content,"reason",reason))return false;
   if(action=="WAIT")
     {direction=action;return true;}
   if(!FlatJSONNumber(content,"entry",entry)||!FlatJSONNumber(content,"sl",stop)||
      !FlatJSONNumber(content,"tp",target))return false;
   if(atr<=0. || MathAbs(entry-close)>InpDecisionMaxEntryDistanceATR*atr)return false;
   const int side=(action=="BUY"?1:-1);
   const double risk=side*(entry-stop),reward=side*(target-entry);
   if(risk<_Point*5 || reward<=0 || risk>6.*atr ||
      reward/risk<InpDecisionMinRR || reward/risk>InpDecisionMaxRR)return false;
   direction=action;return true;
  }

// Preserve the exact data (48 completed bars) as seen by the model at decision time.
// The forward evaluator MUST wait until the NEXT candle OPEN after response time.
void LogClosedBar(const datetime closedTime)
  {
   MqlRates r[];ArraySetAsSeries(r,true);
   if(CopyRates(_Symbol,_Period,1,1,r)!=1)return;
   string line="{\"schema\":1,\"closed_open_server\":"+IntegerToString((long)closedTime)+
     ",\"open\":"+DoubleToString(r[0].open,_Digits)+
     ",\"high\":"+DoubleToString(r[0].high,_Digits)+
     ",\"low\":"+DoubleToString(r[0].low,_Digits)+
     ",\"close\":"+DoubleToString(r[0].close,_Digits)+
     ",\"volume\":"+IntegerToString((long)r[0].tick_volume)+"}";
   if(!AppendNDJSON("bars",line))Print("ALPHA JOURNAL: candle NAO persistido");
  }

void LogDecision(const datetime closeBarTime,const datetime responseTime,
                 const string snapshot,const string raw,const string direction,
                 const double entry,const double sl,const double tp,
                 const string reason,const string status)
  {
   string detail=reason;
   if(StringLen(detail)>InpDecisionMaxTextChars)
      detail=StringSubstr(detail,0,InpDecisionMaxTextChars);
   string rawtrim=raw;
   if(StringLen(rawtrim)>2400)rawtrim=StringSubstr(rawtrim,0,2400);
   string line="{\"schema\":1,\"prompt_version\":\""+NQ_DECISION_PROMPT_VERSION+"\","+
      "\"symbol\":\""+JsonEscape(_Symbol)+"\",\"period\":\"M15\",\"mode\":\"live\","+
      "\"model\":\""+JsonEscape(InpOllamaModel)+"\",\"temperature\":0,"+
      "\"closed_open_server\":"+IntegerToString((long)closeBarTime)+","+
      "\"response_time_server\":"+IntegerToString((long)responseTime)+","+
      "\"direction\":\""+direction+"\",\"entry\":"+DoubleToString(entry,_Digits)+","+
      "\"sl\":"+DoubleToString(sl,_Digits)+",\"tp\":"+DoubleToString(tp,_Digits)+","+
      "\"status\":\""+JsonEscape(status)+"\",\"reason\":\""+JsonEscape(detail)+"\","+
      "\"raw_response\":\""+JsonEscape(rawtrim)+"\",\"input_bars\":"+snapshot+"}";
   if(AppendNDJSON("decisions",line))
     {
      g_decisionCount++;
      g_journalStatus="IA LOG #"+IntegerToString(g_decisionCount)+" "+direction+" / "+status;
      GlobalVariableSet("NXAL_"+IntegerToString((long)AccountInfoInteger(ACCOUNT_LOGIN))+"_"+
                       _Symbol+"_"+IntegerToString((int)_Period), (double)closeBarTime);
     }
   else g_journalStatus="Falha gravando decisao (consulte Diario).";
  }

void RecordOllamaClosedM15()
  {
   if(!InpRecordEveryM15||_Period!=PERIOD_M15||!InpEnableIA||MQLInfoInteger(MQL_TESTER))return;
   const datetime barOpen=iTime(_Symbol,_Period,0);
   const datetime closedOpen=iTime(_Symbol,_Period,1);
   if(barOpen<=0||closedOpen<=0||g_lastRecordAttemptBar==barOpen)return;
   g_lastRecordAttemptBar=barOpen; // never issue duplicate query every 2 sec
   string snapshot=BarsJSON();
   if(StringLen(snapshot)<10)return;
   const string key="NXAL_"+IntegerToString((long)AccountInfoInteger(ACCOUNT_LOGIN))+"_"+
                       _Symbol+"_"+IntegerToString((int)_Period);
   if(GlobalVariableCheck(key) && GlobalVariableGet(key)>=(double)closedOpen)
     {g_journalStatus="Candle ja registrado";return;}
   LogClosedBar(closedOpen);
   string status="ERROR",reason="",direction="WAIT",raw="";
   double entry=0.,sl=0.,tp=0.,atr=0.,close=0.;
   MqlRates b[];ArraySetAsSeries(b,true);
   if(CopyRates(_Symbol,_Period,1,1,b)==1)close=b[0].close;
   ReadVal(g_atr,1,atr);
   if(!ValidOllamaModel(InpOllamaModel) || close<=0. || atr<=0.)
      {reason="Sem modelo valido, barras ou ATR";LogDecision(closedOpen,TimeTradeServer(),snapshot,raw,direction,entry,sl,tp,reason,status);return;}
   string system="Voce e um pesquisador quantitativo. Analise SOMENTE candles fechados. "+
     "Retorne JSON puro com EXATAMENTE as chaves direction (BUY, SELL ou WAIT), entry, sl, tp e reason. "+
     "Numeros como numero JSON, nao strings. Quando WAIT, use entry=0 sl=0 tp=0. "+
     "Nao invente dados externos, noticias nem probabilidade. Um sinal pode perder dinheiro. "+
     "O modelo NAO executa ordens. Nao inclua markdown.";
   string prompt="XAUUSD M15. Atualizado apenas ate o ultimo candle fechado; sem candle futuro. "+
      "Ultimo preco fechado="+DoubleToString(close,_Digits)+", ATR14="+DoubleToString(atr,_Digits)+
      ". Produza proposta ou WAIT; entrada perto do preco atual; SL e TP coerentes com direcao. "+
      "Dados cronologicos OHLCV t(s), o,h,l,c,v: "+snapshot;
   string schema="{\"type\":\"object\",\"properties\":{"+
       "\"direction\":{\"type\":\"string\",\"enum\":[\"BUY\",\"SELL\",\"WAIT\"]},"+
       "\"entry\":{\"type\":\"number\"},\"sl\":{\"type\":\"number\"},"+
       "\"tp\":{\"type\":\"number\"},\"reason\":{\"type\":\"string\"}},"+
       "\"required\":[\"direction\",\"entry\",\"sl\",\"tp\",\"reason\"],"+
       "\"additionalProperties\":false}";
   string body="{\"model\":\""+JsonEscape(InpOllamaModel)+"\",\"stream\":false,"+
       "\"format\":"+schema+",\"messages\":[{\"role\":\"system\",\"content\":\""+
       JsonEscape(system)+"\"},{\"role\":\"user\",\"content\":\""+
       JsonEscape(prompt)+"\"}],\"options\":{\"temperature\":0,\"seed\":42,\"num_predict\":220}}";
   char payload[];StringToCharArray(body,payload,0,WHOLE_ARRAY,CP_UTF8);
   if(ArraySize(payload)>0)ArrayResize(payload,ArraySize(payload)-1);
   char res[];string resHeaders="";
   ResetLastError();
   const int http=WebRequest("POST",NQ_OLLAMA_URL,"Content-Type: application/json\r\n",
      InpOllamaTimeoutMs,payload,res,resHeaders);
   if(http!=200)
     {reason="Ollama HTTP "+IntegerToString(http)+" MT5 "+IntegerToString(GetLastError());}
   else
     {
      string response=CharArrayToString(res,0,ArraySize(res),CP_UTF8);
      if(!OllamaExtractText(response,raw))reason="Ollama resposta HTTP sem message.content";
      else if(DecodePlan(raw,close,atr,direction,entry,sl,tp,reason))status="VALID";
      else
        {status="INVALID";reason="Resposta JSON sem formato/SL/TP/risco valido";direction="WAIT";
         entry=0.;sl=0.;tp=0.;}
     }
   LogDecision(closedOpen,TimeTradeServer(),snapshot,raw,direction,entry,sl,tp,reason,status);
   g_status="Registro Ollama: "+direction+" "+status+" (SEM ORDENS).";
   RefreshTexts();
  }

// Prepare and execute an order selected manually; never from AI response.
bool ExecuteEntry(const int direction,const bool pending)
  {
   // A new candle invalidates the previous manual confirmation/price plan.
   if(iTime(_Symbol,_Period,0)!=g_lastChartBar)
     {g_planReady=false;g_status="Novo candle: reanalise, nenhuma ordem enviada.";return false;}
   if(!ValidTradeAccount())
     {g_status="NEGADO: trading desabilitado / limite diario / conta REAL.";return false;}
   if(!g_planReady&&!ComputePlan())return false;
   if(InpOnlyAlignedTrades && direction!=g_planBias)
     {g_status="NEGADO: direcao nao acompanha EMA21/55; AGUARDAR.";return false;}
   if(AlreadyHasOwnOrderOrPosition()||OtherPositionOnSymbol())
     {g_status="NEGADO: ordem/posicao ja existe no ativo.";return false;}
   MqlTick t;if(!GetTick(t))return false;
   if(InpMaxSpreadUSD>0. && t.ask-t.bid>InpMaxSpreadUSD)
     {g_status="NEGADO: spread acima do maximo.";return false;}
   const double minStop=((double)SymbolInfoInteger(_Symbol,SYMBOL_TRADE_STOPS_LEVEL)+3.0)*_Point;
   double entry=(direction>0?t.ask:t.bid);
   if(pending)
     {
      const double typed=StringToDouble(ObjectGetString(0,N("PRICE"),OBJPROP_TEXT));
      entry=(typed>0.0?typed:(direction>0?g_planBuyLimit:g_planSellLimit));
      entry=TickRound(entry,direction>0);
      // Only supported pending order modes are limit orders, as shown in video.
      if((direction>0&&entry>=t.ask-minStop)||(direction<0&&entry<=t.bid+minStop))
        {g_status="Preco pendente invalido (BUY LIMIT abaixo / SELL LIMIT acima).";return false;}
     }
   if(g_planATR<=0.)return false;
   const double stopDist=MathMax(InpStopATR*g_planATR,2.0*(t.ask-t.bid)+minStop);
   const double stop=TickRound(entry-direction*stopDist,direction>0);
   const double target=TickRound(entry+direction*stopDist*InpTargetR,direction<0);
   if(direction*(entry-stop)<=0. || direction*(target-entry)<=0.)return false;
   const double refBuy=(pending?entry:t.bid);
   const double refSell=(pending?entry:t.ask);
   if(direction>0 && (refBuy-stop<=minStop||target-refBuy<=minStop))
     {g_status="Stops de compra violam distancia minima da corretora.";return false;}
   if(direction<0 && (stop-refSell<=minStop||refSell-target<=minStop))
     {g_status="Stops de venda violam distancia minima da corretora.";return false;}
   ENUM_ORDER_TYPE kind=(direction>0?ORDER_TYPE_BUY:ORDER_TYPE_SELL);
   double lot=RiskVolume(kind,entry,stop);
   if(lot<=0.)
     {g_status="NEGADO: lote minimo excede risco configurado.";return false;}
   double margin=0.;
   if(!OrderCalcMargin(kind,_Symbol,lot,entry,margin)||
      margin>AccountInfoDouble(ACCOUNT_MARGIN_FREE)*InpMaxMarginPct/100.0)
     {g_status="NEGADO: margem insuficiente / alocacao excessiva.";return false;}
   g_trade.SetExpertMagicNumber(InpMagic);
   g_trade.SetDeviationInPoints(InpDeviationPoints);
   g_trade.SetTypeFillingBySymbol(_Symbol);
   bool ok=false;
   if(pending)
     {
      if(direction>0)ok=g_trade.BuyLimit(lot,entry,_Symbol,stop,target,
                                        ORDER_TIME_GTC,0,"NEXUS AI manual BUY LIMIT");
      else ok=g_trade.SellLimit(lot,entry,_Symbol,stop,target,
                               ORDER_TIME_GTC,0,"NEXUS AI manual SELL LIMIT");
     }
   else
     {
      if(direction>0)ok=g_trade.Buy(lot,_Symbol,0.,stop,target,"NEXUS AI manual BUY");
      else ok=g_trade.Sell(lot,_Symbol,0.,stop,target,"NEXUS AI manual SELL");
     }
   uint rc=g_trade.ResultRetcode();
   bool accepted=ok&&(rc==TRADE_RETCODE_DONE||rc==TRADE_RETCODE_DONE_PARTIAL||
                        rc==TRADE_RETCODE_PLACED);
   if(!accepted)
     {g_status="ORDEM RECUSADA MT5: "+IntegerToString((int)rc)+
               " "+g_trade.ResultRetcodeDescription();return false;}
   double fill=(pending?entry:g_trade.ResultPrice());
   if(fill<=0.)fill=entry;
   if(InpDrawTradeLevels)DrawTrade(fill,stop,target);
   g_status=StringFormat("%s %s lot %.2f SL %.2f TP %.2f | servidor aceitou",
             direction>0?"BUY":"SELL",pending?"LIMIT":"MARKET",lot,stop,target);
   return true;
  }

bool CanManageExisting()
  {
   // Risk-reducing actions remain possible even after daily loss halt.
   // They never create a new position or increase risk.
   return MQLInfoInteger(MQL_TESTER)||TerminalInfoInteger(TERMINAL_TRADE_ALLOWED);
  }

bool CancelOwnOrders()
  {
   if(!CanManageExisting()){g_status="Terminal sem permissao para cancelar.";return false;}
   bool ok=true;int count=0;
   for(int i=OrdersTotal()-1;i>=0;i--)
     {
      const ulong ticket=OrderGetTicket(i);
      if(ticket==0||!OrderSelect(ticket))continue;
      if(OrderGetString(ORDER_SYMBOL)!=_Symbol ||
         (ulong)OrderGetInteger(ORDER_MAGIC)!=InpMagic)continue;
      if(!g_trade.OrderDelete(ticket) || g_trade.ResultRetcode()!=TRADE_RETCODE_DONE)
        {ok=false;Print("Falha cancelar ordem ",ticket," ",g_trade.ResultRetcodeDescription());}
      else count++;
     }
   g_status="Canceladas "+IntegerToString(count)+" ordens proprias; "+(ok?"OK":"verificar Journal");
   return ok;
  }

bool CloseOwnPositions()
  {
   if(!CanManageExisting()){g_status="Terminal sem permissao para fechar.";return false;}
   bool ok=true;int count=0;
   for(int i=PositionsTotal()-1;i>=0;i--)
     {
      ulong ticket=PositionGetTicket(i);
      if(ticket==0||!OwnPosition(ticket))continue;
      if(!g_trade.PositionClose(ticket) || g_trade.ResultRetcode()!=TRADE_RETCODE_DONE)
        {ok=false;Print("Falha zerar posicao ",ticket," ",g_trade.ResultRetcodeDescription());}
      else count++;
     }
   g_status="Fechadas "+IntegerToString(count)+" posicoes proprias; "+(ok?"OK":"verificar Journal");
   return ok;
  }

void ReverseOwn()
  {
   if(!ValidTradeAccount()){g_status="Negociacao bloqueada.";return;}
   if(OtherPositionOnSymbol()){g_status="Reversao bloqueada: posicao externa no ativo.";return;}
   int direction=0,count=0;
   for(int i=PositionsTotal()-1;i>=0;i--)
     {
      ulong ticket=PositionGetTicket(i);
      if(ticket==0||!OwnPosition(ticket))continue;
      count++;
      direction=(PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY?-1:1);
     }
   if(count!=1){g_status="Reverter requer exatamente 1 posicao propria.";return;}
   if(InpOnlyAlignedTrades && direction!=g_planBias)
     {g_status="Reversao contraria ao plano tecnico: bloqueada.";return;}
   if(!CloseOwnPositions())return;
   // Reverse uses exactly one explicit double-confirmed event; no AI execution.
   if(!ExecuteEntry(direction,false))Print("Reversao: fechamento OK, nova ordem nao aberta.");
  }

void Action(const string key)
  {
   const bool manual=(key=="BUY"||key=="SELL"||key=="PBUY"||key=="PSELL"||
                      key=="CANCEL"||key=="REVERSE"||key=="FLAT"||key=="ALL");
   if(key=="ANALYZE")
     {g_armedAction="";ComputePlan();RefreshTexts();return;}
   if(key=="ASK_AI")
     {g_armedAction="";AskIA();RefreshTexts();return;}
   if(!manual)return;
   if(g_armedAction!=key || TimeLocal()>g_armExpiry)
     {
      g_armedAction=key;
      g_armExpiry=TimeLocal()+InpConfirmSeconds;
      g_status="CONFIRMAR "+key+": clique NOVAMENTE em ate "+
            IntegerToString(InpConfirmSeconds)+" segundos.";
      RefreshTexts();return;
     }
   g_armedAction="";g_armExpiry=0;
   if(key=="BUY")ExecuteEntry(1,false);
   else if(key=="SELL")ExecuteEntry(-1,false);
   else if(key=="PBUY")ExecuteEntry(1,true);
   else if(key=="PSELL")ExecuteEntry(-1,true);
   else if(key=="CANCEL")CancelOwnOrders();
   else if(key=="FLAT")CloseOwnPositions();
   else if(key=="ALL")
     {bool cancel=CancelOwnOrders();bool flat=CloseOwnPositions();
      g_status=(cancel&&flat?"Ordens proprias canceladas e posicoes fechadas.":
                           "Erro: consulte Journal; alguma operacao pode permanecer.");}
   else if(key=="REVERSE")ReverseOwn();
   RefreshPnL();RefreshTexts();ChartRedraw();
  }

int OnInit()
  {
   if(!IsGoldSymbol())
     {Print("AlphaXAU: utilize apenas XAUUSD/GOLD (sufixos aceitos).");return INIT_PARAMETERS_INCORRECT;}
   int p=PeriodSeconds(_Period);
   if(!(p==60||p==300||p==900||p==1800||p==3600))
     {Print("AlphaXAU: permitido M1/M5/M15/M30/H1.");return INIT_PARAMETERS_INCORRECT;}
   if(InpLookback<10||InpLookback>90||InpATRPeriod<5||InpATRPeriod>100||
      InpStopATR<=0.||InpTargetR<=0.||InpRiskPerTradePct<=0.||
      InpRiskPerTradePct>1.0||InpMaxLots<=0.||InpMaxDailyDrawdownPct<0.||
      InpMaxSpreadUSD<=0.||InpMaxMarginPct<=0.||InpMaxMarginPct>70.||
      InpConfirmSeconds<5||InpConfirmSeconds>30||InpDeviationPoints<0||
      InpOllamaTimeoutMs<1000||InpOllamaTimeoutMs>120000||
      InpDecisionMinRR<0.5||InpDecisionMaxRR<InpDecisionMinRR||
      InpDecisionMaxEntryDistanceATR<=0||InpDecisionMaxTextChars<80)
      return INIT_PARAMETERS_INCORRECT;
   FolderCreate("NexusAlphaXAU",FILE_COMMON);
   g_prefix="NEXUS_ALPHA_"+IntegerToString((long)ChartID())+"_";
   g_atr=iATR(_Symbol,_Period,InpATRPeriod);
   g_ema21=iMA(_Symbol,_Period,21,0,MODE_EMA,PRICE_CLOSE);
   g_ema55=iMA(_Symbol,_Period,55,0,MODE_EMA,PRICE_CLOSE);
   if(g_atr==INVALID_HANDLE||g_ema21==INVALID_HANDLE||g_ema55==INVALID_HANDLE)
      return INIT_FAILED;
   g_trade.SetExpertMagicNumber(InpMagic);
   g_trade.SetDeviationInPoints(InpDeviationPoints);
   g_trade.SetTypeFillingBySymbol(_Symbol);
   g_lastChartBar=iTime(_Symbol,_Period,0);
   g_lastRecordAttemptBar=g_lastChartBar; // first inference ONLY after next closed candle
   RefreshRisk();BuildUI();
   EventSetTimer(2);
   Print("AlphaXAU v1.03: Ollama local direto /api/chat. Trading=",InpTradingEnabled,
         " REAL=",InpAllowReal," | IA=",InpEnableIA,
         ". Nao executa ordens pela IA.");
   return INIT_SUCCEEDED;
  }

void OnDeinit(const int reason)
  {
   EventKillTimer();
   if(g_atr!=INVALID_HANDLE)IndicatorRelease(g_atr);
   if(g_ema21!=INVALID_HANDLE)IndicatorRelease(g_ema21);
   if(g_ema55!=INVALID_HANDLE)IndicatorRelease(g_ema55);
   // Delete only objects created by this EA, NEVER unrelated chart drawings.
   ObjectsDeleteAll(0,g_prefix,0,-1);
   ChartRedraw();
  }

void OnTick()
  {
   // No automated order entry. Even if AI suggests BUY, never send one here.
  }

void OnTimer()
  {
   RefreshPnL();RefreshRisk();
   if(StringLen(g_armedAction)>0 && TimeLocal()>g_armExpiry)
     {g_armedAction="";g_status="Confirmacao expirou; nenhuma ordem enviada.";RefreshTexts();}
   // Don't recalculate levels during an armed manual order.
   datetime now=iTime(_Symbol,_Period,0);
   if(now>0&&now!=g_lastChartBar)
     {g_lastChartBar=now;g_planReady=false;g_armedAction="";
      ObjectDelete(0,N("SUPPORT"));ObjectDelete(0,N("RESISTANCE"));
      ObjectDelete(0,N("LTA"));ObjectDelete(0,N("LTB"));
      ObjectDelete(0,N("ORDER_ZONE"));
      g_status="Novo candle; reanalise antes de operar.";RefreshTexts();
      RecordOllamaClosedM15();}
   ChartRedraw();
  }

void OnChartEvent(const int id,const long &lparam,const double &dparam,
                  const string &sparam)
  {
   if(id==CHARTEVENT_OBJECT_CLICK && StringFind(sparam,g_prefix)==0)
     {
      string key=StringSubstr(sparam,StringLen(g_prefix));
      if(key=="PROMPT"||key=="LOT"||key=="PRICE")return;
      if(ObjectFind(0,sparam)>=0)ObjectSetInteger(0,sparam,OBJPROP_STATE,false);
      Action(key);
     }
   else if(id==CHARTEVENT_OBJECT_ENDEDIT && StringFind(sparam,g_prefix)==0)
     {
      // Changing any editable price/size invalidates prior two-click approval.
      g_armedAction="";
      g_status="Campo editado. Prepare a operacao novamente.";
      RefreshTexts();
     }
  }

void OnTradeTransaction(const MqlTradeTransaction &trans,
                        const MqlTradeRequest &request,
                        const MqlTradeResult &result)
  {
   if(!InpShowExitDots||trans.type!=TRADE_TRANSACTION_DEAL_ADD||trans.deal==0)return;
   if(!HistoryDealSelect(trans.deal))return;
   if(HistoryDealGetString(trans.deal,DEAL_SYMBOL)!=_Symbol ||
      (ulong)HistoryDealGetInteger(trans.deal,DEAL_MAGIC)!=InpMagic)return;
   long entry=HistoryDealGetInteger(trans.deal,DEAL_ENTRY);
   if(entry!=DEAL_ENTRY_OUT && entry!=DEAL_ENTRY_INOUT && entry!=DEAL_ENTRY_OUT_BY)return;
   ulong pid=(ulong)HistoryDealGetInteger(trans.deal,DEAL_POSITION_ID);
   datetime closeTime=(datetime)HistoryDealGetInteger(trans.deal,DEAL_TIME);
   double closePrice=HistoryDealGetDouble(trans.deal,DEAL_PRICE);
   double realized=0.0;
   if(!HistorySelect(0,TimeCurrent()+60))return;
   for(int k=0;k<HistoryDealsTotal();k++)
     {
      ulong tk=HistoryDealGetTicket(k);
      if(tk==0||(ulong)HistoryDealGetInteger(tk,DEAL_POSITION_ID)!=pid)continue;
      realized+=HistoryDealGetDouble(tk,DEAL_PROFIT)+
                HistoryDealGetDouble(tk,DEAL_COMMISSION)+
                HistoryDealGetDouble(tk,DEAL_SWAP);
     }
   string name=N("EXIT_"+IntegerToString((long)trans.deal));
   if(ObjectCreate(0,name,OBJ_ARROW,0,closeTime,closePrice))
     {
      ObjectSetInteger(0,name,OBJPROP_ARROWCODE,159);
      ObjectSetInteger(0,name,OBJPROP_WIDTH,1);
      ObjectSetInteger(0,name,OBJPROP_COLOR,realized>=0.?clrLimeGreen:clrTomato);
      ObjectSetInteger(0,name,OBJPROP_SELECTABLE,false);
      ObjectSetInteger(0,name,OBJPROP_HIDDEN,true);
     }
  }
//+------------------------------------------------------------------+
