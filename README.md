# DEVASTRA TRADING

Options trading strategy using backed market-data and mathematical algorithms

## Setup

```bash
git clone https://github.com/sinetric/devastra-trading.git
cd devastra-trading
```

### Backend setup

Create a virtual environment and install dependencies
```bash
# create the venv
python3 -m venv venv

# activate it
venv\Scripts\activate           # Windows

# install dependencies from requirements.txt
pip install -r requirements.txt
```

### Bot running

Clear logs created by the bot
```bash
python -m src.utils.clear_logs
```