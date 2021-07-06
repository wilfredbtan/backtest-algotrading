import sys
import logging
import time
import datetime as dt
import backtrader as bt

from pprint import pprint
from termcolor import colored

from ccxtbt import CCXTStore, CCXTFeed
from config import EXCHANGE, BINANCE, ENV, PRODUCTION, SANDBOX, DEBUG
# from config import BITFINEX, ENV, PRODUCTION, SANDBOX, COIN_TARGET, COIN_REFER, DEBUG
# from config import KRAKEN, ENV, PRODUCTION, SANDBOX, COIN_TARGET, COIN_REFER, DEBUG
# from config import FTX, ENV, PRODUCTION, SANDBOX, COIN_TARGET, COIN_REFER, DEBUG

from utils import get_trade_analysis, get_sqn, send_telegram_message 

from Sizers import PercValue
from Commissions import CommInfo_Futures_Perc
from strategies import StochMACD, TESTBUY
from Parser import parse_args
from Datasets import *


def main():
    cerebro = bt.Cerebro(quicknotify=True)
    cerebro.broker.set_shortcash(False)

    if ENV == PRODUCTION:  # Live trading with Binance

        broker_config = {
            'apiKey': EXCHANGE.get("key"),
            'secret': EXCHANGE.get("secret"),
            'nonce': lambda: str(int(time.time() * 1000)),
            'enableRateLimit': True,
            # 'verbose': True,
        }

        COIN_TARGET = EXCHANGE.get("coin_target")
        COIN_REFER = EXCHANGE.get("coin_refer")

        store = CCXTStore(
            exchange=EXCHANGE.get("name"),
            # Must have that currency available in order to trade it
            currency=COIN_REFER,
            # symbol=f'{COIN_TARGET}{COIN_REFER}',
            config=broker_config, 
            retries=5, 
            # debug=DEBUG,
            # For Bitfinex
            balance_type=EXCHANGE.get('derivatives', None),
            sandbox=SANDBOX
        )

        # print("exchange methods")
        # pprint(dir(store.exchange))

        symbol = f'{COIN_TARGET}/{COIN_REFER}'
        market = store.exchange.market(symbol)
        # pprint(store.exchange.markets[symbol])

        # balance = store.exchange.fetch_balance({'type': 'margin'})
        # pprint(balance)

        commission = 0.04
        leverage = 5

        if EXCHANGE == BINANCE:
            commission = request_binance_api(store=store, symbol=market['id'], leverage=leverage)

        broker_mapping = {
            'order_types': {
                bt.Order.Market: 'market',
                bt.Order.Limit: 'limit',
                bt.Order.StopLimit: 'stop_market',
                # Bitfinex
                # bt.Order.Market: 'MARKET',
                # bt.Order.Limit: 'LIMIT',
                # bt.Order.StopLimit: 'STOP LIMIT'
            },
            'mappings': {
                'closed_order': {
                    'key': 'status',
                    'value': 'closed'
                },
                'canceled_order': {
                    'key': 'status',
                    'value': 'canceled'
                }
            }
        }

        broker = store.getbroker(broker_mapping=broker_mapping)
        cerebro.setbroker(broker)

        # hist_start_date = dt.datetime.utcnow() - dt.timedelta(hours=1000)
        hist_start_date = dt.datetime.utcnow() - dt.timedelta(minutes=1000)
        data = store.getdata(
            dataname=symbol,
            name=market['id'],
            timeframe=bt.TimeFrame.Minutes,
            fromdate=hist_start_date,
            # compression=60,
            # compression=1,
            # Max number of ticks before throttling occurs
            ohlcv_limit=999,
            # Prevents loading partial data from incomplete candles
            # drop_newest=True
        )

        # Add the feed
        cerebro.adddata(data)

    else:  # Backtesting with CSV file
        dataname = DATASETS.get('btc_hourly')
        data = bt.feeds.GenericCSVData(
            dataname=dataname,
            fromdate=dt.datetime(2017,8,18),
            todate=dt.datetime(2021,6,9),
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
        cerebro.adddata(data)
        broker = cerebro.getbroker()
        broker.setcash(5000.0)

    cashperc = 50

    # Include Strategy
    # cerebro.addstrategy(
    #     StochMACD,
    #     macd1=9,
    #     macd2=21,
    #     macdsig=8,
    #     atrdist=5,
    #     reversal_sensitivity=17,
    #     rsi_upperband=45,
    #     rsi_lowerband=49,
    #     reversal_lowerband=43,
    #     reversal_upperband=48,
    #     leverage=leverage,
    #     loglevel=logging.INFO
    # )

    cerebro.addstrategy(TESTBUY, leverage=leverage, loglevel=logging.INFO)

    print("Commission: ", commission)
    futures_perc = CommInfo_Futures_Perc(commission=commission, leverage=leverage)
    cerebro.broker.addcommissioninfo(futures_perc)

    # Analyzers to evaluate trades and strategies
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name="ta")
    cerebro.addanalyzer(bt.analyzers.SQN, _name="sqn")

    # cerebro.addsizer(PercValue, perc=cashperc, min_size=0.0001)
    cerebro.addsizer(bt.sizers.FixedSize, stake=1)

    # Starting backtrader bot
    initial_value = cerebro.broker.getvalue()
    # (initial_cash, initial_value) = cerebro.broker.get_wallet_balance(currency=COIN_REFER)
    print('Starting Portfolio Value: %.2f' % initial_value)
    datetime_str = dt.datetime.now().strftime('%d %b %Y %H:%M:%S')
    if ENV == PRODUCTION:
        send_telegram_message("== Chart Sniper initialized ==")
        send_telegram_message(f"Date: {datetime_str}")
        send_telegram_message(f"Starting Portfolio Value: {initial_value: .2f}")

    result = cerebro.run()

    # Print analyzers - results
    # (final_cash, final_value) = cerebro.broker.get_wallet_balance(currency=COIN_REFER)
    final_value = cerebro.broker.getvalue()
    final_value_string = f'Final Portfolio Value: {final_value:.2f}'
    profit_string = f'Profit {((final_value - initial_value) / initial_value * 100):.3f}%%'
    ta_string = get_trade_analysis(result[0].analyzers.ta.get_analysis())
    sqn_string = get_sqn(result[0].analyzers.sqn.get_analysis())

    logging.info(final_value_string)
    logging.info(profit_string)
    logging.info(ta_string)
    logging.info(sqn_string)

    if ENV == PRODUCTION:
        telegram_txt = f"```\n{final_value_string}\n{profit_string}\n{ta_string}\n{sqn_string}```"

        datetime_str = dt.datetime.now().strftime('%d %b %Y %H:%M:%S')
        print("Chart Sniper finished by user on %s" % datetime_str)
        send_telegram_message(telegram_txt, parse_mode="Markdown")
        send_telegram_message("Bot finished by user on %s" % datetime_str)


    # if DEBUG:
    #     cerebro.plot()


def request_binance_api(store, symbol, leverage):
    # https://binance-docs.github.io/apidocs/futures/en/#user-api-trading-quantitative-rules-indicators-user_data
    '''
    Change Margin Type
        - POST /fapi/v1/marginType
    Cannot call this if the margin type is already set to the desired type. 
    E.g. If the margin type is CROSSED, setting it to CROSSED again will result in an error
    '''
    # type_response = store.exchange.fapiPrivate_post_margintype ({
    #     'symbol': market['id'],
    #     'marginType': 'CROSSED',
    # })
    # print(type_response)

    # Set leverage multiplier
    '''
    Change Initial Leverage
        - POST /fapi/v1/leverage
    '''
    leverage_response = store.exchange.fapiPrivate_post_leverage({
        'symbol': symbol,
        'leverage': leverage,
    })

    pprint(leverage_response)

    '''
    Get Commision Rate
        - GET /fapi/v1/commissionRate
    {
        "symbol": "BTCUSDT",
        "makerCommissionRate": "0.0002",  // 0.02%
        "takerCommissionRate": "0.0004"   // 0.04%
    }
    '''
    commission_response = store.exchange.fapiPrivate_get_commissionrate ({
        'symbol': symbol
    })
    # print("Get Commission Rate")
    # pprint(commission_response)
    commission = float(commission_response['makerCommissionRate']) * 100

    '''
    Get Open Orders
        - GET /fapi/v1/openOrders
    [
        {
            "avgPrice": "0.00000",
            "clientOrderId": "abc",
            "cumQuote": "0",
            "executedQty": "0",
            "orderId": 1917641,
            "origQty": "0.40",
            "origType": "TRAILING_STOP_MARKET",
            "price": "0",
            "reduceOnly": false,
            "side": "BUY",
            "positionSide": "SHORT",
            "status": "NEW",
            "stopPrice": "9300",                // please ignore when order type is TRAILING_STOP_MARKET
            "closePosition": false,   // if Close-All
            "symbol": "BTCUSDT",
            "time": 1579276756075,              // order time
            "timeInForce": "GTC",
            "type": "TRAILING_STOP_MARKET",
            "activatePrice": "9020",            // activation price, only return with TRAILING_STOP_MARKET order
            "priceRate": "0.3",                 // callback rate, only return with TRAILING_STOP_MARKET order
            "updateTime": 1579276756075,        // update time
            "workingType": "CONTRACT_PRICE",
            "priceProtect": false            // if conditional order trigger is protected   
        }
    ]
    '''
    order_response = store.exchange.fapiPrivate_get_openorders ({
        'symbol': symbol
    })
    # print("Get Order Information")
    # pprint(order_response)
    has_open_orders = len(order_response) > 0
    if has_open_orders:
        txt = "== OPEN ORDERS NOT EXECUTED =="
        print(colored(txt, 'red'))
        if PRODUCTION:
            send_telegram_message(txt)

    '''
    Get Position Information
        - GET /fapi/v2/positionRisk
    [
        {
            "entryPrice": "0.00000",
            "marginType": "isolated", 
            "isAutoAddMargin": "false",
            "isolatedMargin": "0.00000000", 
            "leverage": "10", 
            "liquidationPrice": "0", 
            "markPrice": "6679.50671178",   
            "maxNotionalValue": "20000000", 
            "positionAmt": "0.000", 
            "symbol": "BTCUSDT", 
            "unRealizedProfit": "0.00000000", 
            "positionSide": "BOTH",
        }
    ]
    '''
    position_response = store.exchange.fapiPrivate_get_positionrisk ({
        'symbol': symbol
    })
    # print("Get Position Information")
    # pprint(position_response)
    has_open_positions = len(position_response) > 0 and float(position_response[0]['entryPrice']) != 0
    if has_open_positions:
        txt = "== EXISTING POSITION NOT CLOSED == "
        print(colored(txt, 'red'))
        if PRODUCTION:
            send_telegram_message(txt)
    
    if has_open_positions or has_open_orders:
        raise Exception('Unable to start ChartSniper with existing positions or open orders')

    return commission

if __name__ == "__main__":
    try:
        main()
    except Exception as err:
        datetime_str = dt.datetime.now().strftime('%d %b %Y %H:%M:%S')
        print("Chart Sniper finished with error: ", err)
        send_telegram_message(f"Bot finished with error: {err}\non {datetime_str}", parse_mode=None)
        raise
        # sys.exit(0)
