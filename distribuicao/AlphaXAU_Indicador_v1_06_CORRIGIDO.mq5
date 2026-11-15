//+------------------------------------------------------------------+
//| Nexus AlphaXAU v1.06 | Indicador MQL5 + Ollama local              |
//| TF atual SOMENTE. Pivos S/R confirmados SEM repintar niveis.     |
//| IA: COMPRA / VENDA / AGUARDAR + entrada, SL, TP1 e TP2 visuais.  |
//| NUNCA envia, modifica ou fecha ordens.                           |
//| WebRequest e feito FORA do MT5 por bridge PowerShell local.     |
//+------------------------------------------------------------------+
#property strict
#property version "1.06"
#property indicator_chart_window
#property indicator_buffers 2
#property indicator_plots 2
#property indicator_label1 "EMA 21"
#property indicator_type1 DRAW_LINE
#property indicator_color1 clrDeepSkyBlue
#property indicator_width1 2
#property indicator_label2 "EMA 55"
#property indicator_type2 DRAW_LINE
#property indicator_color2 clrOrange
#property indicator_width2 2
#property description "Indicador TF atual + Ollama: BUY/SELL/WAIT, niveis visuais; S/R confirmado, sem operar."

input group "01 | Indicador / Periodo atual"
input bool InpMostrarEMAs=true;
input bool InpMostrarSuporteResistencia=true;
input bool InpMostrarNiveisIA=true;
input bool InpMostrarTP1=true;
input int InpATRPeriod=14;
input double InpStopATR=1.50;        // SL: 1,5 ATR fechado
input double InpTargetR=1.80;        // TP2: 1,8 x distancia SL (TP1=1R)
input int InpMaxPlotBars=2500;
input group "02 | Suporte e resistencia sem repintar"
input int InpPivotEsquerda=3;        // candles MAIS ANTIGOS
input int InpPivotDireita=3;         // candles MAIS NOVOS, TODOS FECHADOS
input int InpPivosHistoricos=320;    // leitura inicial, nenhuma antecipacao
input int InpMaxLinhasPorLado=3;     // evita poluicao; linhas antigas sao ocultadas, nao movidas
input group "03 | Ollama local"
input bool InpHabilitarOllama=true;
input bool InpConsultaAutomatica=false; // clique manual por padrao
input string InpModelo="llama3.2";
input int InpCandlesEnviados=48;
input int InpTimerSegundos=3;

#define NQ_DIR "NexusAlphaIndicadorTF106"
#define COL_BG C'18,24,33'
#define COL_PANEL C'31,39,49'
#define COL_DIM C'162,175,190'
#define COL_GOLD C'234,193,95'

double g_maFastPlot[],g_maSlowPlot[];
int g_maFast=INVALID_HANDLE,g_maSlow=INVALID_HANDLE,g_atr=INVALID_HANDLE;
string g_prefix="",g_channel="",g_status="Inicializando...";
string g_reason="Sem consulta. Clique CONSULTAR OLLAMA.";
string g_direction="AGUARDAR";
double g_entry=0.,g_sl=0.,g_tp1=0.,g_tp2=0.;
double g_support=0.,g_resistance=0.;
datetime g_lastPivotClosed=0,g_lastAutoClosed=0,g_lastDecisionClosed=0,g_pendingSince=0;
int g_requestSerial=0;
string g_pendingId="";
datetime g_pendingBar=0;
string g_srNames[];
int g_srKinds[]; // 1 fundo, 2 topo; niveis nunca mudam de preco

string Name(const string suffix){return g_prefix+suffix;}
string Num(const double value){return DoubleToString(value,_Digits);}
string TF()
  {
   string name=EnumToString(_Period);
   if(StringFind(name,"PERIOD_")==0)name=StringSubstr(name,7);
   return name;
  }
string CleanId(const string s)
  {
   string v="";
   for(int i=0;i<StringLen(s);i++)
     {
      ushort c=StringGetCharacter(s,i);
      if((c>='A'&&c<='Z')||(c>='a'&&c<='z')||
         (c>='0'&&c<='9')||c=='_'||c=='-')v+=StringSubstr(s,i,1);
      else v+="_";
     }
   return v;
  }
bool ValidModel(const string model)
  {
   if(StringLen(model)<1 || StringLen(model)>80)return false;
   for(int i=0;i<StringLen(model);i++)
     {
      ushort c=StringGetCharacter(model,i);
      if((c>='A'&&c<='Z')||(c>='a'&&c<='z')||
         (c>='0'&&c<='9')||c=='.'||c=='_'||c=='-'||c==':')continue;
      return false;
     }
   return true;
  }
bool ClosedValue(const int handle,const int shift,double &result)
  {
   double a[];
   if(handle==INVALID_HANDLE||CopyBuffer(handle,0,shift,1,a)!=1)return false;
   result=a[0];
   return MathIsValidNumber(result)&&result>0.&&result!=EMPTY_VALUE;
  }
bool WriteFile(const string path,const string value)
  {
   int h=FileOpen(path,FILE_WRITE|FILE_TXT|FILE_ANSI|FILE_COMMON|FILE_SHARE_READ,0,CP_UTF8);
   if(h==INVALID_HANDLE){Print("AlphaXAU: falha ao gravar ",path," err=",GetLastError());return false;}
   FileWriteString(h,value);FileFlush(h);FileClose(h);return true;
  }
bool ReadFile(const string path,string &value)
  {
   value="";
   int h=FileOpen(path,FILE_READ|FILE_TXT|FILE_ANSI|FILE_COMMON|FILE_SHARE_READ,0,CP_UTF8);
   if(h==INVALID_HANDLE)return false;
   long n=FileSize(h);
   if(n>0 && n<12000)value=FileReadString(h,(int)n);
   FileClose(h);
   return StringLen(value)>0;
  }
void Rect(const string tag,const int x,const int y,const int w,const int h,const color bg)
  {
   string obj=Name(tag);
   if(ObjectFind(0,obj)<0)ObjectCreate(0,obj,OBJ_RECTANGLE_LABEL,0,0,0);
   ObjectSetInteger(0,obj,OBJPROP_CORNER,CORNER_LEFT_UPPER);
   ObjectSetInteger(0,obj,OBJPROP_XDISTANCE,x);
   ObjectSetInteger(0,obj,OBJPROP_YDISTANCE,y);
   ObjectSetInteger(0,obj,OBJPROP_XSIZE,w);
   ObjectSetInteger(0,obj,OBJPROP_YSIZE,h);
   ObjectSetInteger(0,obj,OBJPROP_BGCOLOR,bg);
   ObjectSetInteger(0,obj,OBJPROP_COLOR,bg);
   ObjectSetInteger(0,obj,OBJPROP_BACK,false);
   ObjectSetInteger(0,obj,OBJPROP_SELECTABLE,false);
   ObjectSetInteger(0,obj,OBJPROP_HIDDEN,true);
  }
void Label(const string tag,const int x,const int y,const string msg,
           const color col,const int size=9)
  {
   string obj=Name(tag);
   if(ObjectFind(0,obj)<0)ObjectCreate(0,obj,OBJ_LABEL,0,0,0);
   ObjectSetInteger(0,obj,OBJPROP_CORNER,CORNER_LEFT_UPPER);
   ObjectSetInteger(0,obj,OBJPROP_XDISTANCE,x);
   ObjectSetInteger(0,obj,OBJPROP_YDISTANCE,y);
   ObjectSetInteger(0,obj,OBJPROP_COLOR,col);
   ObjectSetInteger(0,obj,OBJPROP_FONTSIZE,size);
   ObjectSetString(0,obj,OBJPROP_FONT,"Segoe UI");
   ObjectSetString(0,obj,OBJPROP_TEXT,msg);
   ObjectSetInteger(0,obj,OBJPROP_SELECTABLE,false);
   ObjectSetInteger(0,obj,OBJPROP_HIDDEN,true);
  }
void Button(const string tag,const int x,const int y,const int w,const string msg)
  {
   string obj=Name(tag);
   if(ObjectFind(0,obj)<0)ObjectCreate(0,obj,OBJ_BUTTON,0,0,0);
   ObjectSetInteger(0,obj,OBJPROP_CORNER,CORNER_LEFT_UPPER);
   ObjectSetInteger(0,obj,OBJPROP_XDISTANCE,x);
   ObjectSetInteger(0,obj,OBJPROP_YDISTANCE,y);
   ObjectSetInteger(0,obj,OBJPROP_XSIZE,w);
   ObjectSetInteger(0,obj,OBJPROP_YSIZE,34);
   ObjectSetInteger(0,obj,OBJPROP_BGCOLOR,C'65,78,112');
   ObjectSetInteger(0,obj,OBJPROP_COLOR,clrWhite);
   ObjectSetInteger(0,obj,OBJPROP_BORDER_COLOR,C'98,121,157');
   ObjectSetString(0,obj,OBJPROP_TEXT,msg);
   ObjectSetInteger(0,obj,OBJPROP_FONTSIZE,9);
   ObjectSetInteger(0,obj,OBJPROP_HIDDEN,true);
  }
void LevelText(const string tag,const double price,const color col)
  {
   const string obj=Name("TEXT_"+tag);
   const datetime at=iTime(_Symbol,_Period,0)+MathMax(60,PeriodSeconds(_Period));
   if(ObjectFind(0,obj)<0)ObjectCreate(0,obj,OBJ_TEXT,0,at,price);
   else ObjectMove(0,obj,0,at,price);
   ObjectSetString(0,obj,OBJPROP_TEXT,tag+" "+Num(price));
   ObjectSetInteger(0,obj,OBJPROP_COLOR,col);
   ObjectSetInteger(0,obj,OBJPROP_FONTSIZE,9);
   ObjectSetString(0,obj,OBJPROP_FONT,"Segoe UI");
   ObjectSetInteger(0,obj,OBJPROP_ANCHOR,ANCHOR_LEFT);
   ObjectSetInteger(0,obj,OBJPROP_SELECTABLE,false);
   ObjectSetInteger(0,obj,OBJPROP_HIDDEN,true);
  }
void Horizontal(const string tag,const double price,const color col,const ENUM_LINE_STYLE style)
  {
   if(!MathIsValidNumber(price)||price<=0.)return;
   const string obj=Name(tag);
   if(ObjectFind(0,obj)<0)ObjectCreate(0,obj,OBJ_HLINE,0,0,price);
   ObjectSetDouble(0,obj,OBJPROP_PRICE,price);
   ObjectSetInteger(0,obj,OBJPROP_COLOR,col);
   ObjectSetInteger(0,obj,OBJPROP_STYLE,style);
   ObjectSetInteger(0,obj,OBJPROP_WIDTH,2);
   ObjectSetInteger(0,obj,OBJPROP_SELECTABLE,false);
   ObjectSetInteger(0,obj,OBJPROP_HIDDEN,true);
   LevelText(tag,price,col);
  }
void ClearPlan()
  {
   string names[4]={"ENTRY","SL","TP1","TP2"};
   for(int i=0;i<4;i++)
     {ObjectDelete(0,Name(names[i]));ObjectDelete(0,Name("TEXT_"+names[i]));}
   g_entry=0.;g_sl=0.;g_tp1=0.;g_tp2=0.;
   Label("PLAN",23,295,"ENTRADA --  |  SL --  |  TP1 --  |  TP2 --",COL_DIM,9);
  }
void BuildPanel()
  {
   Rect("BG",12,18,576,374,COL_BG);
   Rect("HEAD",18,24,564,55,COL_PANEL);
   Label("TITLE",28,32,"NEXUS  |  ALPHA XAU + OLLAMA",clrWhite,11);
   Label("MODE",28,57,"INDICADOR • SOMENTE "+_Symbol+" "+TF()+" • SEM ORDENS",COL_GOLD,8);
   Label("TH",23,91,"TECNICA — CANDLES FECHADOS",COL_GOLD,9);
   Rect("TECH",18,111,564,85,COL_PANEL);
   Label("TREND",28,118,"Regime: aguardando dados...",clrWhite,9);
   Label("SR",28,140,"Pivos confirmados: aguardando...",COL_DIM,8);
   Label("ATR",28,160,"ATR e EMAs: aguardando...",COL_DIM,8);
   Label("PIVOTS",28,180,"S/R confirmado apos 3 candles; nunca movido",COL_GOLD,8);
   Label("AI_HEAD",23,205,"CONSULTA OLLAMA • TIMEFRAME ATUAL",COL_GOLD,9);
   Rect("AIBG",18,225,564,62,COL_PANEL);
   Label("AI_DIR",28,231,"AGUARDAR",clrWhite,11);
   Label("AI_REASON",28,255,"Clique em CONSULTAR OLLAMA para obter orientacao.",COL_DIM,8);
   Label("PLAN",23,295,"ENTRADA --  |  SL --  |  TP1 --  |  TP2 --",COL_DIM,9);
   Button("ASK",22,320,230,"CONSULTAR OLLAMA");
   Label("STATUS",23,362,"Inicializado; aguardando consulta",COL_DIM,8);
   ChartRedraw();
  }

// Uma linha S/R tem ANCORA na ABERTURA DO CANDLE EM QUE O PIVO
// FICOU CONFIRMADO, nao no candle do pivo. Jamais e movida depois.
// Seu historico nao e redesenhado com candles futuros.
void AddPivot(const int side,const datetime confirmedAt,const double price)
  {
   if(confirmedAt<=0 || price<=0.)return;
   const string obj=Name((side==1?"SR_SUPPORT_":"SR_RESIST_")+IntegerToString((long)confirmedAt));
   if(ObjectFind(0,obj)>=0)return;
   if(!InpMostrarSuporteResistencia)
     {if(side==1)g_support=price;else g_resistance=price;return;}
   const int sec=MathMax(60,PeriodSeconds(_Period));
   if(!ObjectCreate(0,obj,OBJ_TREND,0,confirmedAt,price,confirmedAt+sec,price))return;
   ObjectSetInteger(0,obj,OBJPROP_RAY_RIGHT,true);
   ObjectSetInteger(0,obj,OBJPROP_COLOR,(side==1?C'95,152,112':C'172,121,107'));
   ObjectSetInteger(0,obj,OBJPROP_STYLE,STYLE_DOT);
   ObjectSetInteger(0,obj,OBJPROP_WIDTH,1);
   ObjectSetInteger(0,obj,OBJPROP_BACK,true);
   ObjectSetInteger(0,obj,OBJPROP_SELECTABLE,false);
   ObjectSetInteger(0,obj,OBJPROP_HIDDEN,true);
   if(side==1)g_support=price;else g_resistance=price;
   int n=ArraySize(g_srNames);
   ArrayResize(g_srNames,n+1);ArrayResize(g_srKinds,n+1);
   g_srNames[n]=obj;g_srKinds[n]=side;
   int totalSide=0;
   for(int i=0;i<ArraySize(g_srKinds);i++)if(g_srKinds[i]==side)totalSide++;
   if(totalSide>InpMaxLinhasPorLado)
     {
      for(int i=0;i<ArraySize(g_srNames);i++)
        {
         if(g_srKinds[i]!=side)continue;
         // Ocultacao de niveis antigos, sem deslocar preco ou data.
         ObjectDelete(0,g_srNames[i]);
         for(int j=i;j<ArraySize(g_srNames)-1;j++)
           {g_srNames[j]=g_srNames[j+1];g_srKinds[j]=g_srKinds[j+1];}
         ArrayResize(g_srNames,ArraySize(g_srNames)-1);
         ArrayResize(g_srKinds,ArraySize(g_srKinds)-1);
         break;
        }
     }
  }
void ScanPivots(const bool initial)
  {
   MqlRates bars[];ArraySetAsSeries(bars,true);
   const int wanted=InpPivosHistoricos+InpPivotEsquerda+InpPivotDireita+5;
   const int got=CopyRates(_Symbol,_Period,0,wanted,bars);
   if(got<InpPivotEsquerda+InpPivotDireita+7)return;
   if(!initial && bars[1].time==g_lastPivotClosed)return;
   const int youngest=InpPivotDireita+1;  // barra de CONFIRMACAO deve estar fechada
   const int oldest=(initial?MathMin(InpPivosHistoricos,got-InpPivotEsquerda-1):youngest);
   for(int s=oldest;s>=youngest;s--)
     {
      bool pivotHi=true,pivotLo=true;
      for(int k=1;k<=InpPivotEsquerda;k++)
        {if(bars[s].high<=bars[s+k].high)pivotHi=false;
         if(bars[s].low>=bars[s+k].low)pivotLo=false;}
      for(int k=1;k<=InpPivotDireita;k++)
        {if(bars[s].high<bars[s-k].high)pivotHi=false;
         if(bars[s].low>bars[s-k].low)pivotLo=false;}
      const datetime confirmed=bars[s-InpPivotDireita-1].time;
      if(pivotHi)AddPivot(2,confirmed,bars[s].high);
      if(pivotLo)AddPivot(1,confirmed,bars[s].low);
     }
   g_lastPivotClosed=bars[1].time;
  }
void RefreshTechnical()
  {
   MqlRates bars[];ArraySetAsSeries(bars,true);
   if(CopyRates(_Symbol,_Period,0,10,bars)<10)return;
   double fast=0.,slow=0.,priorFast=0.,atr=0.;
   if(!ClosedValue(g_maFast,1,fast)||!ClosedValue(g_maSlow,1,slow)||
      !ClosedValue(g_maFast,6,priorFast)||!ClosedValue(g_atr,1,atr))return;
   string regime="LATERAL / AGUARDAR";
   if(fast>slow && fast>priorFast && bars[1].close>fast)regime="TENDENCIA DE ALTA";
   if(fast<slow && fast<priorFast && bars[1].close<fast)regime="TENDENCIA DE BAIXA";
   Label("TREND",28,118,"Regime: "+regime,clrWhite,9);
   Label("SR",28,140,"Fundo confirmado: "+(g_support>0?Num(g_support):"--")+
         "  |  Topo confirmado: "+(g_resistance>0?Num(g_resistance):"--"),COL_DIM,8);
   Label("ATR",28,160,"ATR14: "+Num(atr)+"  |  EMA21: "+Num(fast)+
         "  |  EMA55: "+Num(slow),COL_DIM,8);
   Label("PIVOTS",28,180,"S/R fixo apos "+IntegerToString(InpPivotDireita)+
         " candles fechados • sem repintar",COL_GOLD,8);
  }

bool QueueRequest(const bool manual)
  {
   if(!InpHabilitarOllama){g_status="Ollama desabilitado nas configuracoes";return false;}
   if(!ValidModel(InpModelo)){g_status="Nome do modelo invalido";return false;}
   if(g_pendingId!=""){g_status="Consulta em andamento; aguarde a resposta";return false;}
   const int needed=InpCandlesEnviados+1;
   MqlRates r[];ArraySetAsSeries(r,true);
   if(CopyRates(_Symbol,_Period,0,needed,r)<needed)
     {g_status="Historico insuficiente no periodo atual";return false;}
   const datetime closed=r[1].time;
   if(closed<=0)return false;
   if(!manual && closed<=g_lastAutoClosed)return false;
   double atr=0.,ema21=0.,ema55=0.;
   if(!ClosedValue(g_atr,1,atr)||!ClosedValue(g_maFast,1,ema21)||
      !ClosedValue(g_maSlow,1,ema55))
     {g_status="Indicadores tecnicos ainda nao prontos";return false;}
   g_requestSerial++;
   const string id=g_channel+"_"+IntegerToString((long)closed)+"_"+
      IntegerToString((long)TimeLocal())+"_"+IntegerToString(g_requestSerial);
   string data="version=2\n";
   data+="id="+id+"\n";
   data+="symbol="+_Symbol+"\nperiod="+TF()+"\n";
   data+="closed_epoch="+IntegerToString((long)closed)+"\n";
   data+="model="+InpModelo+"\n";
   data+="atr="+DoubleToString(atr,6)+"\n";
   data+="ema21="+DoubleToString(ema21,6)+"\n";
   data+="ema55="+DoubleToString(ema55,6)+"\n";
   data+="support="+DoubleToString(g_support,6)+"\n";
   data+="resistance="+DoubleToString(g_resistance,6)+"\n";
   data+="count="+IntegerToString(InpCandlesEnviados)+"\nDATA\n";
   for(int i=InpCandlesEnviados;i>=1;i--)
      data+=IntegerToString((long)r[i].time)+";"+
         DoubleToString(r[i].open,6)+";"+DoubleToString(r[i].high,6)+";"+
         DoubleToString(r[i].low,6)+";"+DoubleToString(r[i].close,6)+";"+
         IntegerToString(r[i].tick_volume)+"\n";
   const string requestPath=NQ_DIR+"\\rq_"+id+".req";
   const string tmp=requestPath+".part";
   if(!WriteFile(tmp,data)){g_status="Erro de gravacao da consulta";return false;}
   if(!FileMove(tmp,FILE_COMMON,requestPath,FILE_COMMON))
     {FileDelete(tmp,FILE_COMMON);g_status="Erro ao publicar consulta";return false;}
   g_pendingId=id;g_pendingBar=closed;g_pendingSince=TimeLocal();
   ClearPlan(); // consulta nova invalida niveis visuais da recomendacao anterior
   g_lastAutoClosed=closed;
   Label("AI_DIR",28,231,"OLLAMA "+TF()+": ANALISANDO...",COL_GOLD,11);
   Label("AI_REASON",28,255,"Aguardando resposta do Llama 3.2 local...",COL_DIM,8);
   g_status="Consulta enviada; sem ordens automaticas";
   return true;
  }

void MarkSignalNow(const string dir,const double price)
  {
   const datetime timestamp=TimeCurrent(); // Horario de resposta, NAO retrocede ao candle analisado
   if(timestamp<=0)return;
   const string obj=Name("SIGNAL_"+IntegerToString((long)timestamp)+"_"+
                          IntegerToString(g_requestSerial));
   if(!ObjectCreate(0,obj,OBJ_ARROW,0,timestamp,price))return;
   ObjectSetInteger(0,obj,OBJPROP_ARROWCODE,(dir=="BUY"?233:234));
   ObjectSetInteger(0,obj,OBJPROP_COLOR,(dir=="BUY"?clrLimeGreen:clrTomato));
   ObjectSetInteger(0,obj,OBJPROP_WIDTH,2);
   ObjectSetInteger(0,obj,OBJPROP_SELECTABLE,false);
   ObjectSetInteger(0,obj,OBJPROP_HIDDEN,true);
   ObjectSetString(0,obj,OBJPROP_TOOLTIP,"Ollama: "+dir+"; sinal criado na resposta, nao no passado");
  }
void HandleResponse(const string id,const datetime bar,const string raw)
  {
   string f[];
   const int n=StringSplit(raw,'|',f);
   if(n<6 || f[0]!=id){g_status="Resposta Ollama invalida (ID/formato)";return;}
   const string dir=f[1],status=f[4];
   const double score=StringToDouble(f[2]);
   if((dir!="BUY"&&dir!="SELL"&&dir!="WAIT") ||
      (status!="OK"&&status!="ERROR") ||
      (status=="ERROR"&&dir!="WAIT") ||
      !MathIsValidNumber(score)||score<0.||score>100.)
     {g_status="IA retornou formato invalido; sem sinal";return;}
   // Nao divulgar sinais que ja venceram enquanto o Llama processava.
   if(iTime(_Symbol,_Period,1)!=bar)
     {g_status="Resposta chegou apos novo candle; descartada";return;}
   ClearPlan();
   g_direction=(dir=="BUY"?"COMPRA":(dir=="SELL"?"VENDA":"AGUARDAR"));
   g_reason=StringSubstr(f[3],0,160);
   g_lastDecisionClosed=bar;
   const color col=(dir=="BUY"?clrLimeGreen:dir=="SELL"?clrTomato:COL_GOLD);
   Label("AI_DIR",28,231,"OLLAMA "+TF()+": "+g_direction+
         "   |  SCORE "+DoubleToString(score,0)+"/100",col,11);
   Label("AI_REASON",28,255,StringSubstr(g_reason,0,85),COL_DIM,8);
   g_status=(status=="OK"?"Resposta registrada • score NAO e chance real":"ERRO Ollama: "+g_reason);
   if(status=="OK" && (dir=="BUY"||dir=="SELL"))
     {
      double atr=0.;
      const int shift=iBarShift(_Symbol,_Period,bar,true);
      MqlTick tick;
      if(shift<1 || !ClosedValue(g_atr,shift,atr)||!SymbolInfoTick(_Symbol,tick))
        {g_status="Sem cotacao/ATR; niveis nao criados";return;}
      const double price=(dir=="BUY"?tick.ask:tick.bid);
      if(price<=0. || !MathIsValidNumber(price))
        {g_status="Cotacao invalida; niveis nao criados";return;}
      const double d=InpStopATR*atr;
      g_entry=NormalizeDouble(price,_Digits);
      g_sl=NormalizeDouble(price+(dir=="BUY"?-1.:1.)*d,_Digits);
      g_tp1=NormalizeDouble(price+(dir=="BUY"?1.:-1.)*d,_Digits);
      g_tp2=NormalizeDouble(price+(dir=="BUY"?1.:-1.)*d*InpTargetR,_Digits);
      if(InpMostrarNiveisIA)
        {
         Horizontal("ENTRY",g_entry,C'202,197,104',STYLE_DASH);
         Horizontal("SL",g_sl,clrTomato,STYLE_DASH);
         if(InpMostrarTP1)Horizontal("TP1",g_tp1,C'105,185,125',STYLE_DOT);
         Horizontal("TP2",g_tp2,clrLimeGreen,STYLE_DASH);
        }
      MarkSignalNow(dir,g_entry+(dir=="BUY"?-.25:.25)*atr);
      Label("PLAN",23,295,"ENTRADA "+Num(g_entry)+" | SL "+Num(g_sl)+
            " | TP1 "+Num(g_tp1)+" | TP2 "+Num(g_tp2),clrWhite,8);
     }
   else Label("PLAN",23,295,"AGUARDAR: sem entrada, TP ou SL nesta consulta",COL_DIM,9);
   // Journal inclui timestamp de resposta, nunca retrodata a entrada.
   const string journal=NQ_DIR+"\\historico_"+g_channel+".csv";
   int h=FileOpen(journal,FILE_READ|FILE_WRITE|FILE_TXT|FILE_ANSI|FILE_COMMON|
                  FILE_SHARE_READ|FILE_SHARE_WRITE,0,CP_UTF8);
   if(h!=INVALID_HANDLE)
     {
      if(FileSize(h)==0)FileWriteString(h,
         "id;closed_epoch;response_epoch;period;direction;score;entry_quote;sl;tp1;tp2;status;reason\r\n");
      FileSeek(h,0,SEEK_END);
      string reason=g_reason;StringReplace(reason,";",",");StringReplace(reason,"\n"," ");
      FileWriteString(h,id+";"+IntegerToString((long)bar)+";"+
         IntegerToString((long)StringToInteger(f[5]))+";"+TF()+";"+dir+";"+
         DoubleToString(score,0)+";"+Num(g_entry)+";"+Num(g_sl)+";"+
         Num(g_tp1)+";"+Num(g_tp2)+";"+status+";"+reason+"\r\n");
      FileClose(h);
     }
  }
void PollResponse()
  {
   if(g_pendingId=="")return;
   string raw="";
   if(!ReadFile(NQ_DIR+"\\rs_"+g_pendingId+".rsp",raw))return;
   HandleResponse(g_pendingId,g_pendingBar,raw);
   g_pendingId="";g_pendingBar=0;g_pendingSince=0;
  }

int OnInit()
  {
   if(InpATRPeriod<3||InpStopATR<=0.||InpTargetR<=0.||
      InpCandlesEnviados<24||InpCandlesEnviados>128||
      InpPivotEsquerda<1||InpPivotEsquerda>12||
      InpPivotDireita<1||InpPivotDireita>12||
      InpPivosHistoricos<50||InpPivosHistoricos>3000||
      InpMaxLinhasPorLado<1||InpMaxLinhasPorLado>12||
      InpTimerSegundos<1||InpTimerSegundos>60||InpMaxPlotBars<100)
      return INIT_PARAMETERS_INCORRECT;
   SetIndexBuffer(0,g_maFastPlot,INDICATOR_DATA);
   SetIndexBuffer(1,g_maSlowPlot,INDICATOR_DATA);
   ArraySetAsSeries(g_maFastPlot,true);ArraySetAsSeries(g_maSlowPlot,true);
   PlotIndexSetDouble(0,PLOT_EMPTY_VALUE,EMPTY_VALUE);
   PlotIndexSetDouble(1,PLOT_EMPTY_VALUE,EMPTY_VALUE);
   IndicatorSetString(INDICATOR_SHORTNAME,"Nexus AlphaXAU Ollama TF atual v1.06");
   g_maFast=iMA(_Symbol,_Period,21,0,MODE_EMA,PRICE_CLOSE);
   g_maSlow=iMA(_Symbol,_Period,55,0,MODE_EMA,PRICE_CLOSE);
   g_atr=iATR(_Symbol,_Period,InpATRPeriod);
   if(g_maFast==INVALID_HANDLE||g_maSlow==INVALID_HANDLE||g_atr==INVALID_HANDLE)
      return INIT_FAILED;
   if(!InpMostrarEMAs)
     {PlotIndexSetInteger(0,PLOT_DRAW_TYPE,DRAW_NONE);
      PlotIndexSetInteger(1,PLOT_DRAW_TYPE,DRAW_NONE);}
   g_prefix="NXIND106_"+IntegerToString((long)ChartID())+"_";
   g_channel=CleanId(_Symbol)+"_"+CleanId(TF());
   FolderCreate(NQ_DIR,FILE_COMMON);
   g_lastAutoClosed=iTime(_Symbol,_Period,1);
   BuildPanel();ScanPivots(true);RefreshTechnical();
   EventSetTimer(InpTimerSegundos);
   if(StringFind(_Symbol,"XAUUSD")<0 && StringFind(_Symbol,"GOLD")<0)
      g_status="Indicador desenhado para XAUUSD / GOLD";
   return INIT_SUCCEEDED;
  }
int OnCalculate(const int rates_total,const int prev_calculated,
                const datetime &time[],const double &open[],const double &high[],
                const double &low[],const double &close[],const long &tick_volume[],
                const long &volume[],const int &spread[])
  {
   if(rates_total<80)return 0;
   int n=(prev_calculated==0?MathMin(rates_total,InpMaxPlotBars):
          MathMin(rates_total,MathMax(3,rates_total-prev_calculated+3)));
   if(prev_calculated==0)
     {ArrayInitialize(g_maFastPlot,EMPTY_VALUE);ArrayInitialize(g_maSlowPlot,EMPTY_VALUE);}
   double a[],b[];ArraySetAsSeries(a,true);ArraySetAsSeries(b,true);
   if(CopyBuffer(g_maFast,0,0,n,a)!=n||CopyBuffer(g_maSlow,0,0,n,b)!=n)
      return prev_calculated;
   for(int i=0;i<n;i++){g_maFastPlot[i]=a[i];g_maSlowPlot[i]=b[i];}
   return rates_total;
  }
void OnTimer()
  {
   PollResponse();
   if(g_pendingId!="" && g_pendingSince>0 && TimeLocal()-g_pendingSince>180)
     {
      g_pendingId="";g_pendingBar=0;g_pendingSince=0;
      g_status="Ollama sem resposta (>180s). Verifique a bridge e tente novamente.";
     }
   const datetime closed=iTime(_Symbol,_Period,1);
   if(closed>0 && closed!=g_lastPivotClosed)
     {
      ScanPivots(false);
      if(g_entry>0. && g_lastDecisionClosed!=closed)
        {ClearPlan();g_status="Novo candle fechado: consulte Ollama novamente";}
     }
   RefreshTechnical();
   if(InpConsultaAutomatica && InpHabilitarOllama &&
      closed>0 && closed>g_lastAutoClosed)QueueRequest(false);
   Label("STATUS",23,362,StringSubstr(g_status,0,100),COL_DIM,8);
   ChartRedraw();
  }
void OnChartEvent(const int id,const long &lparam,const double &dparam,
                  const string &sparam)
  {
   if(id!=CHARTEVENT_OBJECT_CLICK)return;
   if(sparam==Name("ASK"))
     {
      QueueRequest(true);
      ObjectSetInteger(0,sparam,OBJPROP_STATE,false);
      ChartRedraw();
     }
  }
void OnDeinit(const int reason)
  {
   EventKillTimer();
   if(g_maFast!=INVALID_HANDLE)IndicatorRelease(g_maFast);
   if(g_maSlow!=INVALID_HANDLE)IndicatorRelease(g_maSlow);
   if(g_atr!=INVALID_HANDLE)IndicatorRelease(g_atr);
   for(int i=ObjectsTotal(0,0,-1)-1;i>=0;i--)
     {
      string obj=ObjectName(0,i,0,-1);
      if(StringFind(obj,g_prefix)==0)ObjectDelete(0,obj);
     }
   ChartRedraw();
  }
//+------------------------------------------------------------------+