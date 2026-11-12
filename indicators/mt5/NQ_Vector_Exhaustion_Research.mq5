//+------------------------------------------------------------------+
//| NQ_Vector_Exhaustion_Research.mq5                                 |
//| Independent educational study of public candle-vector geometry.  |
//| NOT Greenhouse Tracker source, clone or license. No broker trades.|
//+------------------------------------------------------------------+
#property copyright "Nexus Quant independent research"
#property link      "https://github.com/lulualcides-sys/nexus-quant-paper"
#property version   "0.10"
#property description "Independent non-repainting candle sweep/volume study."
#property description "Signals are NOT the proprietary Greenhouse Tracker signals."
#property indicator_chart_window
#property indicator_buffers 2
#property indicator_plots   2

#property indicator_label1 "NQ Compra (pesquisa)"
#property indicator_type1  DRAW_ARROW
#property indicator_color1 clrLimeGreen
#property indicator_width1 2

#property indicator_label2 "NQ Venda (pesquisa)"
#property indicator_type2  DRAW_ARROW
#property indicator_color2 clrTomato
#property indicator_width2 2

input int      InpLookbackBars       = 20;     // Prior COMPLETED bars, same local chart day
input double   InpVolumeFactor       = 1.30;   // Hypothesis, NOT original Tracker threshold
input double   InpMinWickFraction    = 0.35;   // Hypothesis: directional wick / candle range
input double   InpMinSweepPoints     = 5.0;    // Prior high/low excursion
input double   InpMinRangePoints     = 30.0;   // Avoid micro candles
input double   InpMaxRangePoints     = 450.0;  // Avoid event-sized candles
input bool     InpRequireRealVolume  = true;   // Strict volume for WIN, never fake contract counts
input int      InpHistoryBars        = 900;    // Initial historical scan ceiling
input int      InpLineHorizonBars    = 20;     // Levels are only chart guides
input bool     InpDrawExtraLevels   = true;   // 0 and 100 in addition to entry/stop/target
input bool     InpAlertOnNewSignal  = false;  // Visual alert, never sends orders

double BuyArrow[];
double SellArrow[];
datetime gLastOpen = 0;
string gPrefix;

// Unidirectional candle index: 0 is STILL FORMING; 1 is last CLOSED.
// Series arrays are explicitly set in OnCalculate. Never inspect bar 0.
bool DetectClosedSignal(const int i,const int count,
                        const datetime &times[], const double &opens[],
                        const double &highs[], const double &lows[],
                        const double &closes[], const long &ticks[],
                        const long &volumes[], int &side)
{
   side=0;
   if(i<1 || i+InpLookbackBars>=count)
      return false;
   const double range=highs[i]-lows[i];
   if(range<InpMinRangePoints || range>InpMaxRangePoints)
      return false;

   const string day=TimeToString(times[i],TIME_DATE);
   double priorHigh=-DBL_MAX;
   double priorLow=DBL_MAX;
   double volumeSum=0.0;
   for(int j=i+1;j<=i+InpLookbackBars;j++)
   {
      if(TimeToString(times[j],TIME_DATE)!=day)
         return false; // No blending sessions
      priorHigh=MathMax(priorHigh,highs[j]);
      priorLow=MathMin(priorLow,lows[j]);
      const double v=InpRequireRealVolume?(double)volumes[j]:(double)ticks[j];
      if(v<=0.0)
         return false; // No fabricated trade volume
      volumeSum+=v;
   }

   const double currentVol=InpRequireRealVolume?(double)volumes[i]:(double)ticks[i];
   if(currentVol<=0 || currentVol<InpVolumeFactor*volumeSum/InpLookbackBars)
      return false;
   const double lowerWick=MathMin(opens[i],closes[i])-lows[i];
   const double upperWick=highs[i]-MathMax(opens[i],closes[i]);
   const bool isBuy=(lows[i]<=priorLow-InpMinSweepPoints &&
                     closes[i]>priorLow && closes[i]>opens[i] &&
                     lowerWick/range>=InpMinWickFraction);
   const bool isSell=(highs[i]>=priorHigh+InpMinSweepPoints &&
                      closes[i]<priorHigh && closes[i]<opens[i] &&
                      upperWick/range>=InpMinWickFraction);
   if(isBuy==isSell) return false; // Both/none ambiguous
   side=isBuy?1:-1;
   return true;
}

void DrawLevel(const string signalId,const string suffix,
               const datetime start,const double level,
               const color shade,const ENUM_LINE_STYLE style)
{
   const string objectName=gPrefix+signalId+"_"+suffix;
   if(ObjectFind(0,objectName)>=0)
      return; // Once confirmed the level is NEVER moved/recomputed by ticks
   datetime endTime=start+(datetime)((long)PeriodSeconds(_Period)*(long)InpLineHorizonBars);
   if(!ObjectCreate(0,objectName,OBJ_TREND,0,start,level,endTime,level))
   {
      Print("NQ level creation failed: ",objectName," error ",GetLastError());
      return;
   }
   ObjectSetInteger(0,objectName,OBJPROP_COLOR,shade);
   ObjectSetInteger(0,objectName,OBJPROP_WIDTH,1);
   ObjectSetInteger(0,objectName,OBJPROP_STYLE,style);
   ObjectSetInteger(0,objectName,OBJPROP_RAY_RIGHT,false);
   ObjectSetInteger(0,objectName,OBJPROP_RAY_LEFT,false);
   ObjectSetInteger(0,objectName,OBJPROP_SELECTABLE,false);
   ObjectSetInteger(0,objectName,OBJPROP_HIDDEN,true);
   ObjectSetString(0,objectName,OBJPROP_TOOLTIP,suffix+"  "+DoubleToString(level,_Digits));
}

void DrawVector(const int i,const int side,
                const datetime &times[],const double &highs[],
                const double &lows[])
{
   const double r=highs[i]-lows[i];
   const double origin=(side>0)?lows[i]:highs[i];
   const double direction=(side>0)?1.0:-1.0;
   const double p0=origin;
   const double p50=origin+direction*0.5*r;
   const double p100=origin+direction*r;
   const double p200=origin+direction*2.0*r;
   const double pm100=origin-direction*r;
   const string id=(side>0?"BUY_":"SELL_")+IntegerToString((long)times[i]);

   // All levels are GUIDE prices. No assumption of actual filled entry.
   DrawLevel(id,"ENTRY_50",times[i],p50,clrGold,STYLE_SOLID);
   DrawLevel(id,"TARGET_200",times[i],p200,clrLimeGreen,STYLE_DASH);
   DrawLevel(id,"STOP_NEG100",times[i],pm100,clrTomato,STYLE_DASH);
   if(InpDrawExtraLevels)
   {
      DrawLevel(id,"BASE_0",times[i],p0,clrSilver,STYLE_DOT);
      DrawLevel(id,"BASE_100",times[i],p100,clrSilver,STYLE_DOT);
   }
}

// Never draw an arrow on forming candle 0, even during first attach.
void Evaluate(const int i,const int total,
              const datetime &times[],const double &opens[],
              const double &highs[],const double &lows[],
              const double &closes[],const long &ticks[],
              const long &volumes[])
{
   BuyArrow[i]=EMPTY_VALUE;
   SellArrow[i]=EMPTY_VALUE;
   int side=0;
   if(!DetectClosedSignal(i,total,times,opens,highs,lows,closes,ticks,volumes,side))
      return;
   if(side>0)
      BuyArrow[i]=lows[i]-0.15*(highs[i]-lows[i]);
   else
      SellArrow[i]=highs[i]+0.15*(highs[i]-lows[i]);
   DrawVector(i,side,times,highs,lows);
   if(InpAlertOnNewSignal && i==1 && gLastOpen!=0)
      Alert("NQ Vector Exhaustion RESEARCH: ",(side>0?"COMPRA":"VENDA"),
            " ",_Symbol," ",TimeToString(times[i],TIME_DATE|TIME_MINUTES));
}

int OnInit()
{
   if(InpLookbackBars<5 || InpVolumeFactor<1.0 ||
      InpMinWickFraction<0.0 || InpMinWickFraction>1.0 ||
      InpMinRangePoints<=0 || InpMinRangePoints>=InpMaxRangePoints ||
      InpMinSweepPoints<0 || InpHistoryBars<50 ||
      InpLineHorizonBars<1)
   {
      Print("Invalid independent research input parameters");
      return INIT_PARAMETERS_INCORRECT;
   }
   if(_Period!=PERIOD_M1)
      Print("NQ warning: M1 is the intended video reference; this chart is not M1.");
   SetIndexBuffer(0,BuyArrow,INDICATOR_DATA);
   SetIndexBuffer(1,SellArrow,INDICATOR_DATA);
   ArraySetAsSeries(BuyArrow,true);
   ArraySetAsSeries(SellArrow,true);
   PlotIndexSetInteger(0,PLOT_ARROW,233);
   PlotIndexSetInteger(1,PLOT_ARROW,234);
   PlotIndexSetDouble(0,PLOT_EMPTY_VALUE,EMPTY_VALUE);
   PlotIndexSetDouble(1,PLOT_EMPTY_VALUE,EMPTY_VALUE);
   IndicatorSetString(INDICATOR_SHORTNAME,"NQ Vector Exhaustion (independent research)");
   gPrefix="NQVE_"+IntegerToString((long)ChartID())+"_";
   gLastOpen=0;
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   ObjectsDeleteAll(0,gPrefix,0,-1);
}

int OnCalculate(const int rates_total,const int prev_calculated,
                const datetime &time[],const double &open[],
                const double &high[],const double &low[],const double &close[],
                const long &tick_volume[],const long &volume[],
                const int &spread[])
{
   if(rates_total<InpLookbackBars+3)
      return 0;
   ArraySetAsSeries(time,true);
   ArraySetAsSeries(open,true);
   ArraySetAsSeries(high,true);
   ArraySetAsSeries(low,true);
   ArraySetAsSeries(close,true);
   ArraySetAsSeries(tick_volume,true);
   ArraySetAsSeries(volume,true);
   BuyArrow[0]=EMPTY_VALUE;
   SellArrow[0]=EMPTY_VALUE;

   if(prev_calculated==0)
   {
      ArrayInitialize(BuyArrow,EMPTY_VALUE);
      ArrayInitialize(SellArrow,EMPTY_VALUE);
      ObjectsDeleteAll(0,gPrefix,0,-1); // history revised: derive only from closed bars
      const int oldest=MathMin(InpHistoryBars,rates_total-InpLookbackBars-1);
      for(int i=oldest;i>=1;i--)
         Evaluate(i,rates_total,time,open,high,low,close,tick_volume,volume);
   }
   else if(gLastOpen!=time[0])
   {
      // Called once on new bar: previous bar is now immutable and closed.
      Evaluate(1,rates_total,time,open,high,low,close,tick_volume,volume);
   }
   gLastOpen=time[0];
   return rates_total;
}
//+------------------------------------------------------------------+
