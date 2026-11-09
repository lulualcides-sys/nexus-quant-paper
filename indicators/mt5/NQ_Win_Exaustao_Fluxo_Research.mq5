//+------------------------------------------------------------------+
//| NQ_Win_Exaustao_Fluxo_Research.mq5                               |
//| INDICADOR INDEPENDENTE - NAO E O TRACKER ORIGINAL.               |
//| Only CLOSED WIN M1 candles + real classified trade ticks.       |
//| DOES NOT PLACE ORDERS OR ACCESS AN ACCOUNT.                     |
//+------------------------------------------------------------------+
#property copyright "Nexus Quant - original independent research"
#property link      "https://github.com/lulualcides-sys/nexus-quant-paper"
#property version   "0.200"
#property description "WIN M1: confirmed absorption/exhaustion against classified exchange trades"
#property description "Independent indicator. NOT Greenhouse Tracker, not validated for trading."
#property indicator_chart_window
#property indicator_buffers 2
#property indicator_plots 2
#property indicator_label1 "NQ Exaustao compra (pesquisa)"
#property indicator_type1 DRAW_ARROW
#property indicator_color1 clrLimeGreen
#property indicator_width1 2
#property indicator_label2 "NQ Exaustao venda (pesquisa)"
#property indicator_type2 DRAW_ARROW
#property indicator_color2 clrTomato
#property indicator_width2 2

input int      InpLookbackBars           = 20;   // Prior closed candles; same server day
input int      InpHistoryScanBars        = 90;   // Limit costly historical tick requests
input double   InpBarVolumeMultiplier    = 1.15; // Hypothesis, not Tracker parameter
input int      InpMinimumClassifiedTicks = 25;   // Minimum properly classified trades
input double   InpMinClassifiedShare     = 0.60; // Share of all trade volume with direction flags
input double   InpContraAggressorShare   = 0.56; // Sell pressure for buys / buy pressure for sells
input double   InpMinimumWickFraction    = 0.15;
input double   InpCloseLocation          = 0.60;
input double   InpMinCandlePoints        = 30.0;
input double   InpMaxCandlePoints        = 400.0;
input double   InpSweepByPoints          = 5.0;  // Minimum sweep of earlier extreme
input double   InpNearExtremePoints      = 50.0; // Absorption alternative near support/resistance
input int      InpSignalMethod           = 2;    // 0=sweep, 1=absorption, 2=either
input bool     InpVerifyTickCoverage     = true; // Verify tick coverage near open/close
input bool     InpRequireWIN             = true;
input int      InpLineHorizonBars        = 20;
input bool     InpShowExtraLevels        = false;
input bool     InpAlertOnNewBar          = false;

double BufferBuy[];
double BufferSell[];
string gPrefix;
datetime gBarOpen = 0;
int gRejectedNoTickFlow = 0;
int gRejectedPrice = 0;
int gSignals = 0;

bool IsWINContract(const string s)
{
   if(StringLen(s)!=6 || StringSubstr(s,0,3)!="WIN")
      return false;
   const string code=StringSubstr(s,3,1);
   if(StringFind("GJMQVZ",code)<0) return false;
   const int y1=(int)StringGetCharacter(s,4);
   const int y2=(int)StringGetCharacter(s,5);
   return y1>=48 && y1<=57 && y2>=48 && y2<=57;
}

double TickRound(const double price)
{
   double tick=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE);
   if(tick<=0) return NormalizeDouble(price,_Digits);
   return NormalizeDouble(MathRound(price/tick)*tick,_Digits);
}

// Buy-side aggression = executed trades flagged TICK_FLAG_BUY, not
// "positive candles" or an invented split of total volume.
bool ClassifiedContraFlow(const datetime candleStart,int &direction,
                          double &contraShare,double &classifiedCoverage,
                          double &observedVolume)
{
   direction=0;
   contraShare=0.0;
   classifiedCoverage=0.0;
   observedVolume=0.0;
   MqlTick trades[];
   const ulong fromMs=(ulong)candleStart*1000;
   const ulong toMs=fromMs+(ulong)PeriodSeconds(_Period)*1000-1;
   ResetLastError();
   const int received=CopyTicksRange(_Symbol,trades,COPY_TICKS_TRADE,fromMs,toMs);
   if(received<=0) {gRejectedNoTickFlow++;return false;}

   double buyVol=0.0,sellVol=0.0,unknownVol=0.0;
   int classifiedEvents=0;
   long firstStamp=-1,lastStamp=-1;
   for(int k=0;k<received;k++)
   {
      const uint flags=trades[k].flags;
      const bool buy=(flags&TICK_FLAG_BUY)!=0;
      const bool sell=(flags&TICK_FLAG_SELL)!=0;
      if(!buy && !sell)
      {
         // Price/volume updates without an aggressor flag cannot be classified.
         // Count genuine volume as unknown, never infer a side.
         if((flags&TICK_FLAG_VOLUME)!=0 && trades[k].volume_real>0)
            unknownVol+=trades[k].volume_real;
         continue;
      }
      if(buy==sell) continue; // invalid BOTH flags
      const double v=trades[k].volume_real;
      if(v<=0.0) continue; // no genuine executed size
      if(trades[k].time_msc<(long)fromMs ||
         trades[k].time_msc>(long)toMs)
         continue;
      if(firstStamp<0) firstStamp=trades[k].time_msc;
      lastStamp=trades[k].time_msc;
      if(buy) buyVol+=v; else sellVol+=v;
      classifiedEvents++;
   }
   const double classified=buyVol+sellVol;
   observedVolume=classified+unknownVol;
   if(classifiedEvents<InpMinimumClassifiedTicks || classified<=0.0)
   {
      gRejectedNoTickFlow++;return false;
   }
   classifiedCoverage=classified/(classified+unknownVol);
   if(classifiedCoverage<InpMinClassifiedShare)
   {
      gRejectedNoTickFlow++;return false;
   }
   if(InpVerifyTickCoverage)
   {
      // Silence of the venue is possible, but historical truncation is worse.
      // This conservative sanity guard does not PROVE completeness.
      if(firstStamp<0 || firstStamp>(long)(fromMs+15000) ||
         lastStamp<(long)(toMs-15000))
      {
         gRejectedNoTickFlow++;return false;
      }
   }
   contraShare=MathMax(buyVol,sellVol)/classified;
   if(contraShare<InpContraAggressorShare)
      return false;
   // Price-side direction to be decided by actual CLOSE, not ticks alone.
   direction=(sellVol>buyVol)?1:-1; // Heavy sells absorbed -> BUY reversal
   return true;
}

bool PriceExhaustion(const int i,const int total,
                     const datetime &ts[],const double &o[],
                     const double &h[],const double &l[],
                     const double &c[],const long &realVolume[],
                     bool &buyCandidate,bool &sellCandidate)
{
   buyCandidate=false; sellCandidate=false;
   if(i<1 || i+InpLookbackBars>=total)
      return false;
   double range=h[i]-l[i];
   if(range<InpMinCandlePoints || range>InpMaxCandlePoints)
      return false;
   if((double)realVolume[i]<=0) return false;

   const string session=TimeToString(ts[i],TIME_DATE);
   double sumVolume=0.0,priorHigh=-DBL_MAX,priorLow=DBL_MAX;
   for(int j=i+1;j<=i+InpLookbackBars;j++)
   {
      if(TimeToString(ts[j],TIME_DATE)!=session || realVolume[j]<=0)
         return false;
      sumVolume+=(double)realVolume[j];
      priorHigh=MathMax(priorHigh,h[j]);
      priorLow=MathMin(priorLow,l[j]);
   }
   if((double)realVolume[i]<InpBarVolumeMultiplier*sumVolume/InpLookbackBars)
      return false;

   const double pos=(c[i]-l[i])/range;
   const double lowerWick=(MathMin(o[i],c[i])-l[i])/range;
   const double upperWick=(h[i]-MathMax(o[i],c[i]))/range;
   const bool buySweep=(l[i]<=priorLow-InpSweepByPoints && c[i]>priorLow);
   const bool sellSweep=(h[i]>=priorHigh+InpSweepByPoints && c[i]<priorHigh);
   const bool buyAbs=(l[i]<=priorLow+InpNearExtremePoints);
   const bool sellAbs=(h[i]>=priorHigh-InpNearExtremePoints);
   const bool buyMethod=InpSignalMethod==0?buySweep:
                        (InpSignalMethod==1?buyAbs:(buySweep||buyAbs));
   const bool sellMethod=InpSignalMethod==0?sellSweep:
                         (InpSignalMethod==1?sellAbs:(sellSweep||sellAbs));
   buyCandidate=buyMethod && c[i]>o[i] && pos>=InpCloseLocation &&
                lowerWick>=InpMinimumWickFraction;
   sellCandidate=sellMethod && c[i]<o[i] && pos<=(1.0-InpCloseLocation) &&
                 upperWick>=InpMinimumWickFraction;
   return buyCandidate!=sellCandidate;
}

void DrawPrice(const string id,const string type,
               const datetime t,const double price,
               const color clr,const ENUM_LINE_STYLE style,
               const string why)
{
   const string key=gPrefix+id+"_"+type;
   if(ObjectFind(0,key)>=0) return; // Do not move historical guides
   const double level=TickRound(price);
   const datetime expiry=t+(datetime)(PeriodSeconds(_Period)*InpLineHorizonBars);
   if(!ObjectCreate(0,key,OBJ_TREND,0,t,level,expiry,level))
      return;
   ObjectSetInteger(0,key,OBJPROP_COLOR,clr);
   ObjectSetInteger(0,key,OBJPROP_STYLE,style);
   ObjectSetInteger(0,key,OBJPROP_WIDTH,1);
   ObjectSetInteger(0,key,OBJPROP_RAY_RIGHT,false);
   ObjectSetInteger(0,key,OBJPROP_SELECTABLE,false);
   ObjectSetInteger(0,key,OBJPROP_HIDDEN,true);
   ObjectSetString(0,key,OBJPROP_TOOLTIP,type+" | "+
                   DoubleToString(level,_Digits)+" | "+why);
}

void DrawVector(const int i,const int side,const datetime &t[],
                const double &h[],const double &l[],
                const double contra,const double coverage)
{
   const double range=h[i]-l[i];
   const double origin=side==1?l[i]:h[i];
   const double d=(double)side;
   const string id=(side==1?"B":"S")+IntegerToString((long)t[i]);
   const string details="NQ investigacao: fluxo contra="+
                        DoubleToString(contra*100,1)+"%; classificados="+
                        DoubleToString(coverage*100,1)+"%";
   // Public geometric concept; not evidence of an actual filled order.
   DrawPrice(id,"ENTRY_50",t[i],origin+d*0.5*range,clrGold,STYLE_SOLID,details);
   DrawPrice(id,"TARGET_200",t[i],origin+d*2.0*range,clrLimeGreen,STYLE_DASH,details);
   DrawPrice(id,"STOP_NEG100",t[i],origin-d*range,clrTomato,STYLE_DASH,details);
   if(InpShowExtraLevels)
   {
      DrawPrice(id,"FIBO_0",t[i],origin,clrSilver,STYLE_DOT,details);
      DrawPrice(id,"FIBO_100",t[i],origin+d*range,clrSilver,STYLE_DOT,details);
   }
}

void EvaluateClosed(const int i,const int total,
                    const datetime &t[],const double &o[],
                    const double &h[],const double &l[],
                    const double &c[],const long &realVolume[])
{
   BufferBuy[i]=EMPTY_VALUE;
   BufferSell[i]=EMPTY_VALUE;
   bool buy=false,sell=false;
   if(!PriceExhaustion(i,total,t,o,h,l,c,realVolume,buy,sell))
   {
      gRejectedPrice++;return;
   }
   int flowDirection=0;
   double contra=0.0,coverage=0.0,traded=0.0;
   if(!ClassifiedContraFlow(t[i],flowDirection,contra,coverage,traded))
      return;
   if((buy && flowDirection!=1)||(sell && flowDirection!=-1))
      return; // Trade delta must contradict the candle's successful reversal

   const int side=buy?1:-1;
   if(buy) BufferBuy[i]=l[i]-0.12*(h[i]-l[i]);
   else BufferSell[i]=h[i]+0.12*(h[i]-l[i]);
   DrawVector(i,side,t,h,l,contra,coverage);
   gSignals++;
   if(InpAlertOnNewBar && i==1 && gBarOpen!=0)
      Alert("NQ Fluxo Exaustao PESQUISA ",_Symbol," ",
            (buy?"COMPRA":"VENDA")," candle ",
            TimeToString(t[i],TIME_DATE|TIME_MINUTES));
}

int OnInit()
{
   if(InpRequireWIN && !IsWINContract(_Symbol))
   {
      Print("NQ: Somente WIN com vencimento explicito; nao WINFUT.");
      return INIT_PARAMETERS_INCORRECT;
   }
   if(_Period!=PERIOD_M1)
   {
      Print("NQ: Use somente grafico M1 para esta pesquisa.");
      return INIT_PARAMETERS_INCORRECT;
   }
   const double grid=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE);
   if(MathAbs(grid-5.0)>0.001)
   {
      Print("NQ: Produto nao apresenta tick WIN de 5 pontos. Abortando.");
      return INIT_PARAMETERS_INCORRECT;
   }
   if(InpLookbackBars<5 || InpHistoryScanBars<1 ||
      InpBarVolumeMultiplier<1.0 || InpMinimumClassifiedTicks<5 ||
      InpMinClassifiedShare<=0 || InpMinClassifiedShare>1 ||
      InpContraAggressorShare<=0.50 || InpContraAggressorShare>1 ||
      InpMinimumWickFraction<0 || InpMinimumWickFraction>1 ||
      InpCloseLocation<0.5 || InpCloseLocation>1 ||
      InpMinCandlePoints<=0 || InpMinCandlePoints>=InpMaxCandlePoints ||
      InpSweepByPoints<0 || InpNearExtremePoints<0 ||
      InpLineHorizonBars<1 || InpSignalMethod<0 || InpSignalMethod>2)
      return INIT_PARAMETERS_INCORRECT;

   SetIndexBuffer(0,BufferBuy,INDICATOR_DATA);
   SetIndexBuffer(1,BufferSell,INDICATOR_DATA);
   ArraySetAsSeries(BufferBuy,true);
   ArraySetAsSeries(BufferSell,true);
   PlotIndexSetInteger(0,PLOT_ARROW,233);
   PlotIndexSetInteger(1,PLOT_ARROW,234);
   PlotIndexSetDouble(0,PLOT_EMPTY_VALUE,EMPTY_VALUE);
   PlotIndexSetDouble(1,PLOT_EMPTY_VALUE,EMPTY_VALUE);
   IndicatorSetString(INDICATOR_SHORTNAME,"NQ Exaustao de Fluxo (independente)");
   gPrefix="NQFLOW_"+IntegerToString((long)ChartID())+"_";
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   ObjectsDeleteAll(0,gPrefix,0,-1);
   Print("NQ independent flow experiment. Signals=",gSignals,
         ", rejected_price=",gRejectedPrice,
         ", rejected_no_flow=",gRejectedNoTickFlow);
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
   ArraySetAsSeries(volume,true);
   // Candle index 0 is not closed. NEVER calculate a signal on it.
   BufferBuy[0]=EMPTY_VALUE;
   BufferSell[0]=EMPTY_VALUE;

   if(prev_calculated==0)
   {
      ArrayInitialize(BufferBuy,EMPTY_VALUE);
      ArrayInitialize(BufferSell,EMPTY_VALUE);
      ObjectsDeleteAll(0,gPrefix,0,-1);
      const int oldest=MathMin(InpHistoryScanBars,rates_total-InpLookbackBars-1);
      // Backwards only affects performance, not future price data. The
      // detector at i reads i+1..i+lookback, older CLOSED candles only.
      for(int i=oldest;i>=1;i--)
         EvaluateClosed(i,rates_total,time,open,high,low,close,volume);
   }
   else if(gBarOpen!=time[0])
   {
      EvaluateClosed(1,rates_total,time,open,high,low,close,volume);
   }
   gBarOpen=time[0];
   return rates_total;
}
//+------------------------------------------------------------------+
