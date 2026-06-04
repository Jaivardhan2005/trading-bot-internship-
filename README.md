quick start

cp .env.example .env          # fill in your testnet key & secret
pip install -r requirements.txt
python cli.py ping             # verify connectivity
python cli.py place-order --symbol BTCUSDT --side BUY --type MARKET --quantity 0.001
python cli.py place-order --symbol BTCUSDT --side SELL --type LIMIT --quantity 0.001 --price 108000
