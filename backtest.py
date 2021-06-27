import backtrader as bt
import time
from datetime import datetime

from Commissions import CommInfo_Futures_Perc_Mult
from Parser import parse_args
from Datasets import *
from strategies import StochMACD, WfaStochMACD
from utils import print_sqn, print_trade_analysis

def runstrat(args=None):
    args = parse_args(args)

    # Need to disable the stdstats for optimization
    cerebro = bt.Cerebro(optreturn=(not args.optimize), quicknotify=True, stdstats=False)

    cerebro.broker.set_shortcash(False)
    cerebro.broker.set_cash(args.cash)
    cerebro.broker.setcommission(commission=0.00015, leverage=args.leverage)

    fromdate = datetime.strptime(args.fromdate, '%Y-%m-%d')
    todate = datetime.strptime(args.todate, '%Y-%m-%d')

    dataname1 = DATASETS.get(args.dataset)
    data = bt.feeds.GenericCSVData(
        dataname=dataname1,
        fromdate=fromdate,
        todate=todate,
        timeframe=bt.TimeFrame.Minutes,
        nullvalue=0.0,
        datetime=0,
        open=4,
        high=5,
        low=6,
        close=7,
        volume=8,
        compression=60,
        headers=True,
    )

    # dataname2 = DATASETS.get(args.dataset2)
    # data2 = bt.feeds.GenericCSVData(
    #     dataname=dataname2,
    #     fromdate=fromdate,
    #     todate=todate,
    #     timeframe=bt.TimeFrame.Minutes,
    #     nullvalue=0.0,
    #     datetime=0,
    #     open=4,
    #     high=5,
    #     low=6,
    #     close=7,
    #     volume=8,
    #     compression=1,
    #     headers=True,
    # )


    # https://www.backtrader.com/docu/data-multitimeframe/data-multitimeframe/
    #  data with the smallest timeframe (and thus the larger number of bars) must be the 1st one to be added to the Cerebro instance
    # cerebro.resampledata(data2, timeframe=bt.TimeFrame.Minutes, compression=15)
    # cerebro.resampledata(data2, timeframe=bt.TimeFrame.Minutes, compression=60)
    cerebro.adddata(data)
    cerebro.resampledata(data, timeframe=bt.TimeFrame.Minutes, compression=240)

    if args.optimize:
        cerebro.optstrategy(StochMACD, 
            # macd1=range(7, 15),
            # macd2=range(18, 26),
            # macdsig=range(7, 10),
            macd1=9,
            macd2=21,
            macdsig=8,
            # macd1=10,
            # macd2=16,
            # macdsig=5,

            # atrdist=range(1,10),
            atrdist=5,

            # reversal_sensitivity=range(5, 20),
            reversal_sensitivity=17,

            rsi_upperband=range(40,55),
            rsi_lowerband=range(40,55),

            # reversal_lowerband=range(40,53),
            # reversal_upperband=range(45,55),
            reversal_lowerband=43,
            reversal_upperband=48,

            # leverage=args.leverage,
            # leverage=(1,125),
            leverage=5,

            isWfa=False,
        )
        
        cerebro.addanalyzer(bt.analyzers.SQN, _name="sqn")

        optimized_runs = cerebro.run()

        final_results_list = []

        for run in optimized_runs:
            for strategy in run:
                sqn = strategy.analyzers.sqn.get_analysis()
                PnL = round(strategy.broker.get_value() - args.cash, 2)
                final_results_list.append(
                    [
                        sqn['sqn'],
                        PnL, 
                        # strategy.p.atrdist,
                        # strategy.p.macd1, 
                        # strategy.p.macd2, 
                        # strategy.p.macdsig, 
                        # strategy.p.reversal_sensitivity, 
                        # strategy.p.reversal_lowerband,
                        # strategy.p.reversal_upperband,
                        # strategy.p.leverage, 
                        strategy.p.rsi_upperband,
                        strategy.p.rsi_lowerband,
                    ]
                )
        sort_by_analyzer = sorted(final_results_list, key=lambda x: x[0], reverse=True)
        for line in sort_by_analyzer[:5]:
            print(line)

    else:
        cerebro.addstrategy(StochMACD, 
            # interval_params=interval_params,
            macd1=args.macd1,
            macd2=args.macd2,
            macdsig=args.macdsig,
            stoch_k_period=args.stoch_k_period,
            stoch_d_period=args.stoch_d_period,
            stoch_rsi_period=args.stoch_rsi_period,
            stoch_period=args.stoch_period,
            stoch_upperband=args.stoch_upperband,
            stoch_lowerband=args.stoch_lowerband,
            rsi_upperband=args.rsi_upperband,
            rsi_lowerband=args.rsi_lowerband,
            # mfi_upperband=50,
            # mfi_lowerband=50,
            cmf_upperband=0.0,
            cmf_lowerband=-0.0,
            atrperiod=args.atrperiod,
            atrdist=args.atrdist,
            reversal_sensitivity=args.reversal_sensitivity,
            reversal_lowerband=args.reversal_lowerband,
            reversal_upperband=args.reversal_upperband,
            loglevel=args.loglevel,
            leverage=args.leverage,
            cashperc=args.cashperc,
            isWfa=False,
        )

        cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name="ta")
        cerebro.addanalyzer(bt.analyzers.SQN, _name="sqn")
        cerebro.addobserver(bt.observers.Value)

        initial_value = cerebro.broker.getvalue()
        print('Starting Portfolio Value: %.2f' % initial_value)
        result = cerebro.run()

        # Print analyzers - results
        final_value = cerebro.broker.getvalue()
        print('Final Portfolio Value: %.2f' % final_value)
        print('Profit %.3f%%' % ((final_value - initial_value) / initial_value * 100))
        print_trade_analysis(result[0].analyzers.ta.get_analysis())
        print_sqn(result[0].analyzers.sqn.get_analysis())

        sqn = result[0].analyzers.sqn.get_analysis()
        PnL = round(result[0].broker.get_value() - args.cash, 2)
        print(
            [
                sqn['sqn'],
                PnL, 
                result[0].p.atrdist,
                result[0].p.macd1, 
                result[0].p.macd2, 
                result[0].p.macdsig, 
                result[0].p.reversal_sensitivity, 
                result[0].p.rsi_upperband,
                result[0].p.rsi_upperband,
                result[0].p.reversal_lowerband,
                result[0].p.reversal_upperband,
                # result[0].p.leverage, 
            ]
        )

        if args.plot:
            cerebro.plot()

if __name__ == '__main__':
    start_time = time.time()
    runstrat()
    print("--- %s seconds ---" % (time.time() - start_time))
