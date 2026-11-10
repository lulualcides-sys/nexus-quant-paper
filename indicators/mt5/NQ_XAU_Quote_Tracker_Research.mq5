//+------------------------------------------------------------------+
//| NQ_XAU_Quote_Tracker_Research.mq5                                |
//| Independent XAUUSD closed-bar quote-activity research indicator. |
//| NOT original Tracker; NO real aggressor delta or institutional    |
//| flow. NEVER sends orders. OTC broker ticks != executed volume.   |
//+------------------------------------------------------------------+
#property copyright "Nexus Quant - independent research"
#property link      "https://github.com/lulualcides-sys/nexus-quant-paper"
#property version   "1.000"
#property description "XAUUSD M1/M5: quote-activity exhaustion/sweep research"
#property description "NOT the Greenhouse Tracker. Tick count is not trade aggression."
#property indicator_chart_window
#property indicator_buffers 2
#property indicator_plots 2
#property indicator_label1 "NQ XAU COMPRA (pesquisa)"
#property indicator_type1 DRAW_ARROW
#property indicator_color1 clrLimeGreen
#property indicator_width1 2
#property indicator_label2 "NQ XAU VENDA (pesquisa)"
#property indicator_type2 DRAW_ARROW
#property indicator_color2 clrTomato
#property indicator_width2 2

input int      InpLookbackBars        = 20;    // Only PRIOR closed bars
input int      InpATRPeriod          = 14;    // Only PRIOR bars, not signal bar
input int      InpHistoryScanBars    = 450;
input int      InpMinTickUpdates     = 15;    // Broker QUOTE updates, NOT volume traded
input double   InpActivityMultiplier = 1.20;  // Activity vs earlier quote-update average
input double   InpMinRangeATR        = 0.60;
input double   InpMaxRangeATR        = 2.50;
input double   InpMinimumWick        = 0.28;
input double   InpCloseLocation      = 0.62;
input double   InpSweepATR           = 0.06;
input double   InpMaxSpreadATR       = 0.35;  // M1/M5 historical broker spread proxy
input int      InpLineHorizonBars    = 20;
input bool     InpDrawExtraLevels    = true;   // Public candle 0-100% guides
input bool     InpDrawPriceLabels    = true;   // Entry 50 / Target 200 / Stop -100
input bool     InpDrawSignalText     = true;   // COMPRA / VENDA labels
input bool     InpRequireLiquidityZone = false;// Optional independent hypothesis
input int      InpLiquidityMinTouches = 2;    // Older repeat tests of a prior extreme
input double   InpLiquidityToleranceATR = 0.18;// Proximity of repeated quote lows/highs
input bool     InpAlertOnNewBar      = false;

double BufferBuy[];
double BufferSell[];
string gPrefix;
datetime gLastOpen=0;
int gResearchSignals=0;

bool IsXAUUSD(const string symbol)
{
   string upper=symbol;
   StringToUpper(upper);
   // Allow broker suffixes such as XAUUSD.a; never treat GC=F or WIN as XAU.
   return StringFind(upper,"XAUUSD")==0 && StringLen(upper)<=24;
}

double AlignBrokerTick(const double price)
{
   double tick=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE);
   if(tick<=0.0) tick=_Point;
   return NormalizeDouble(MathRound(price/tick)*tick,_Digits);
}

bool GoodCandle(const int j,const datetime &times[],const double &opens[],
                const double &highs[],const double &lows[],const double &closes[],
                const long &ticks[],const int &spreads[])
{
   const double o=opens[j],h=highs[j],l=lows[j],c=closes[j];
   if(times[j]<=0 || ticks[j]<=0 || spreads[j]<0 ||
      !MathIsValidNumber(o) || !MathIsValidNumber(h) ||
      !MathIsValidNumber(l) || !MathIsValidNumber(c) ||
      l<=0.0 || l>MathMin(o,c) || MathMax(o,c)>h || h<=l)
      return false;
   return true;
}

// NEVER touches the unfinished candle 0, nor any future candle i-1.
// All thresholds are hypotheses, not the proprietary Tracker settings.
int ResearchSignal(const int i,const int total,
                   const datetime &times[],const double &opens[],
                   const double &highs[],const double &lows[],const double &closes[],
                   const long &ticks[],const int &spreads[])
{
   const int larger=(InpLookbackBars>InpATRPeriod?InpLookbackBars:InpATRPeriod);
   const int required=larger+1;
   if(i<1 || i+required>=total)
      return 0;
   const int tf=PeriodSeconds(_Period);
   // Reject gaps instead of silently blending weekends/discontinuous quotes.
   for(int j=i;j<=i+required;j++)
   {
      if(!GoodCandle(j,times,opens,highs,lows,closes,ticks,spreads))
         return 0;
      if(j>i)
      {
         const long gap=(long)times[j-1]-(long)times[j];
         if(gap<=0 || gap>2*(long)tf) return 0;
      }
   }

   // ATR is computed solely from previous CLOSED candles.
   double sumTR=0.0;
   for(int j=i+1;j<=i+InpATRPeriod;j++)
   {
      const double priorClose=closes[j+1];
      const double tr=MathMax(highs[j]-lows[j],
                       MathMax(MathAbs(highs[j]-priorClose),
                               MathAbs(lows[j]-priorClose)));
      sumTR+=tr;
   }
   const double atr=sumTR/InpATRPeriod;
   const double range=highs[i]-lows[i];
   if(atr<=0.0 || range<InpMinRangeATR*atr || range>InpMaxRangeATR*atr)
      return 0;

   double priorLow=DBL_MAX,priorHigh=-DBL_MAX,tickTotal=0.0;
   for(int j=i+1;j<=i+InpLookbackBars;j++)
   {
      priorLow=MathMin(priorLow,lows[j]);
      priorHigh=MathMax(priorHigh,highs[j]);
      tickTotal+=(double)ticks[j];
   }
   if(ticks[i]<InpMinTickUpdates ||
      (double)ticks[i]<InpActivityMultiplier*tickTotal/InpLookbackBars)
      return 0;
   // Spread is historical broker metadata, NOT a guaranteed executable fill.
   // If missing (<=0), fail closed rather than assume a zero-cost spread.
   if(spreads[i]<=0 || (double)spreads[i]*_Point>InpMaxSpreadATR*atr)
      return 0;

   const double location=(closes[i]-lows[i])/range;
   const double lowerWick=(MathMin(opens[i],closes[i])-lows[i])/range;
   const double upperWick=(highs[i]-MathMax(opens[i],closes[i]))/range;
   const bool buy=lows[i]<=priorLow-InpSweepATR*atr &&
                  closes[i]>priorLow && closes[i]>opens[i] &&
                  location>=InpCloseLocation && lowerWick>=InpMinimumWick;
   const bool sell=highs[i]>=priorHigh+InpSweepATR*atr &&
                   closes[i]<priorHigh && closes[i]<opens[i] &&
                   location<=1.0-InpCloseLocation && upperWick>=InpMinimumWick;
   if(InpRequireLiquidityZone)
   {
      // Optional research proxy: two or more OLD price touches at the extreme.
      // Not a claim about proprietary Greenhouse flow or exact signal rules.
      const double tol=InpLiquidityToleranceATR*atr;
      int lowsTouched=0,highsTouched=0;
      for(int j=i+1;j<=i+InpLookbackBars;j++)
      {
         if(MathAbs(lows[j]-priorLow)<=tol) lowsTouched++;
         if(MathAbs(highs[j]-priorHigh)<=tol) highsTouched++;
      }
      if(buy && lowsTouched<InpLiquidityMinTouches) return 0;
      if(sell && highsTouched<InpLiquidityMinTouches) return 0;
   }
   if(buy==sell) return 0;
   return buy?1:-1;
}

void DrawLevel(const string id,const string suffix,const datetime originTime,
               const double price,const color tone,const ENUM_LINE_STYLE style)
{
   const string key=gPrefix+id+"_"+suffix;
   if(ObjectFind(0,key)>=0) return; // No shifting finalized chart guides
   const datetime expiry=originTime+(datetime)((long)PeriodSeconds(_Period)*InpLineHorizonBars);
   const double p=AlignBrokerTick(price);
   if(!ObjectCreate(0,key,OBJ_TREND,0,originTime,p,expiry,p))
      return;
   ObjectSetInteger(0,key,OBJPROP_COLOR,tone);
   ObjectSetInteger(0,key,OBJPROP_STYLE,style);
   ObjectSetInteger(0,key,OBJPROP_WIDTH,1);
   ObjectSetInteger(0,key,OBJPROP_RAY_RIGHT,false);
   ObjectSetInteger(0,key,OBJPROP_SELECTABLE,false);
   ObjectSetInteger(0,key,OBJPROP_HIDDEN,true);
   ObjectSetString(0,key,OBJPROP_TOOLTIP,
      "NQ XAU research "+suffix+" "+DoubleToString(p,_Digits)+
      " | quote activity, NOT aggressor flow");
   if(InpDrawPriceLabels)
   {
      const string labelKey=key+"_TEXT";
      const datetime labelTime=originTime+
            (datetime)((long)PeriodSeconds(_Period)*(long)MathMax(2,InpLineHorizonBars/2));
      if(ObjectCreate(0,labelKey,OBJ_TEXT,0,labelTime,p))
      {
         ObjectSetInteger(0,labelKey,OBJPROP_COLOR,tone);
         ObjectSetInteger(0,labelKey,OBJPROP_FONTSIZE,9);
         ObjectSetInteger(0,labelKey,OBJPROP_ANCHOR,ANCHOR_LEFT);
         ObjectSetInteger(0,labelKey,OBJPROP_SELECTABLE,false);
         ObjectSetInteger(0,labelKey,OBJPROP_HIDDEN,true);
         ObjectSetString(0,labelKey,OBJPROP_FONT,"Arial");
         ObjectSetString(0,labelKey,OBJPROP_TEXT,suffix+"  "+DoubleToString(p,_Digits));
      }
   }
}

void DrawResearchVector(const int i,const int side,const datetime &times[],
                        const double &highs[],const double &lows[])
{
   const double span=highs[i]-lows[i];
   const double origin=(side==1?lows[i]:highs[i]);
   const double s=(double)side;
   const string id=(side==1?"BUY_":"SELL_")+IntegerToString((long)times[i]);
   // Same PUBLIC Tracker-style candle geometry; no fill or performance claim.
   // Entry 50, target 200, stop -100 imply nominal 1:1, NOT 2:1.
   DrawLevel(id,"ENTRY_50",times[i],origin+s*0.50*span,clrGold,STYLE_SOLID);
   DrawLevel(id,"TARGET_200",times[i],origin+s*2.00*span,clrLimeGreen,STYLE_DASH);
   DrawLevel(id,"STOP_NEG100",times[i],origin-s*span,clrTomato,STYLE_DASH);
   if(InpDrawExtraLevels)
   {
      DrawLevel(id,"BASE_0",times[i],origin,clrSilver,STYLE_DOT);
      DrawLevel(id,"BASE_100",times[i],origin+s*span,clrSilver,STYLE_DOT);
   }
}

void EvaluateClosed(const int i,const int total,
                    const datetime &times[],const double &opens[],
                    const double &highs[],const double &lows[],const double &closes[],
                    const long &ticks[],const int &spreads[])
{
   BufferBuy[i]=EMPTY_VALUE;
   BufferSell[i]=EMPTY_VALUE;
   const int side=ResearchSignal(i,total,times,opens,highs,lows,closes,ticks,spreads);
   if(side==0) return;
   const double span=highs[i]-lows[i];
   if(side==1) BufferBuy[i]=lows[i]-0.12*span;
   else BufferSell[i]=highs[i]+0.12*span;
   if(InpDrawSignalText)
   {
      const string labelKey=gPrefix+"SIGNAL_"+IntegerToString((long)times[i]);
      const double labelPrice=side==1?lows[i]-0.27*span:highs[i]+0.27*span;
      if(ObjectFind(0,labelKey)<0 &&
         ObjectCreate(0,labelKey,OBJ_TEXT,0,times[i],labelPrice))
      {
         ObjectSetInteger(0,labelKey,OBJPROP_COLOR,side==1?clrLimeGreen:clrTomato);
         ObjectSetInteger(0,labelKey,OBJPROP_FONTSIZE,9);
         ObjectSetInteger(0,labelKey,OBJPROP_ANCHOR,ANCHOR_CENTER);
         ObjectSetInteger(0,labelKey,OBJPROP_SELECTABLE,false);
         ObjectSetInteger(0,labelKey,OBJPROP_HIDDEN,true);
         ObjectSetString(0,labelKey,OBJPROP_TEXT,side==1?"COMPRA":"VENDA");
      }
   }
   DrawResearchVector(i,side,times,highs,lows);
   gResearchSignals++;
   if(InpAlertOnNewBar && i==1 && gLastOpen!=0)
      Alert("NQ XAU quote TRACKER PESQUISA ",_Symbol," ",
            side==1?"COMPRA":"VENDA"," candle fechado ",
            TimeToString(times[i],TIME_DATE|TIME_MINUTES));
}

int OnInit()
{
   if(!IsXAUUSD(_Symbol))
   {
      Print("NQ XAU research only: use broker symbol starting XAUUSD.");
      return INIT_PARAMETERS_INCORRECT;
   }
   if(_Period!=PERIOD_M1 && _Period!=PERIOD_M5)
   {
      Print("NQ XAU research requires M1 or M5. No automatic trading.");
      return INIT_PARAMETERS_INCORRECT;
   }
   if(InpLookbackBars<5 || InpATRPeriod<2 || InpHistoryScanBars<1 ||
      InpMinTickUpdates<1 || InpActivityMultiplier<1 ||
      InpMinRangeATR<=0 || InpMinRangeATR>=InpMaxRangeATR ||
      InpMinimumWick<0 || InpMinimumWick>1 ||
      InpCloseLocation<0.5 || InpCloseLocation>1 ||
      InpSweepATR<0 || InpMaxSpreadATR<=0 ||
      InpLiquidityMinTouches<2 || InpLiquidityMinTouches>InpLookbackBars ||
      InpLiquidityToleranceATR<0 ||
      InpLineHorizonBars<2 || _Point<=0)
      return INIT_PARAMETERS_INCORRECT;
   SetIndexBuffer(0,BufferBuy,INDICATOR_DATA);
   SetIndexBuffer(1,BufferSell,INDICATOR_DATA);
   ArraySetAsSeries(BufferBuy,true);
   ArraySetAsSeries(BufferSell,true);
   PlotIndexSetInteger(0,PLOT_ARROW,233);
   PlotIndexSetInteger(1,PLOT_ARROW,234);
   PlotIndexSetDouble(0,PLOT_EMPTY_VALUE,EMPTY_VALUE);
   PlotIndexSetInteger(0,PLOT_DRAW_BEGIN,InpLookbackBars+InpATRPeriod+2);
   PlotIndexSetInteger(1,PLOT_DRAW_BEGIN,InpLookbackBars+InpATRPeriod+2);
   IndicatorSetString(INDICATOR_SHORTNAME,
      "NQ XAU quote Tracker (independent, no real delta)");
   gPrefix="NQXAU_"+IntegerToString((long)ChartID())+"_";
   gLastOpen=0;
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   ObjectsDeleteAll(0,gPrefix,0,-1);
   Print("NQ XAU RESEARCH only: arrows=",gResearchSignals,
         ". No broker order, trade-side aggression or P&L validation.");
}

int OnCalculate(const int rates_total,const int prev_calculated,
                const datetime &time[],const double &open[],
                const double &high[],const double &low[],const double &close[],
                const long &tick_volume[],const long &volume[],
                const int &spread[])
{
   const int required=(InpLookbackBars>InpATRPeriod?InpLookbackBars:InpATRPeriod)+1;
   if(rates_total<required+3) return 0;
   ArraySetAsSeries(time,true);
   ArraySetAsSeries(open,true);
   ArraySetAsSeries(high,true);
   ArraySetAsSeries(low,true);
   ArraySetAsSeries(close,true);
   ArraySetAsSeries(tick_volume,true);
   ArraySetAsSeries(spread,true);
   // No current unfinished candle can EVER trigger a signal.
   BufferBuy[0]=EMPTY_VALUE;
   BufferSell[0]=EMPTY_VALUE;
   if(prev_calculated==0)
   {
      ArrayInitialize(BufferBuy,EMPTY_VALUE);
      ArrayInitialize(BufferSell,EMPTY_VALUE);
      ObjectsDeleteAll(0,gPrefix,0,-1);
      const int oldest=MathMin(InpHistoryScanBars,rates_total-required-1);
      for(int i=oldest;i>=1;i--)
         EvaluateClosed(i,rates_total,time,open,high,low,close,tick_volume,spread);
   }
   else if(gLastOpen!=time[0])
   {
      // Recover EVERY newly closed candle after a pause, not just index 1.
      // Bound runtime and retain the same no-lookahead rule.
      int oldestNew=0;
      for(int i=1;i<rates_total-required && i<=InpHistoryScanBars;i++)
      {
         if(gLastOpen>0 && time[i]<=gLastOpen) break;
         oldestNew=i;
      }
      for(int i=oldestNew;i>=1;i--)
         EvaluateClosed(i,rates_total,time,open,high,low,close,tick_volume,spread);
   }
   gLastOpen=time[0];
   return rates_total;
}
//+------------------------------------------------------------------+
