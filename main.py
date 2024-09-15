import discord, datetime, sqlite3, json, random, os
from discord.ext import commands, tasks
from matplotlib import pyplot
import matplotlib.font_manager as fm
from dotenv import load_dotenv

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)
dbCon = sqlite3.connect('stock.db')
dbCon.row_factory = sqlite3.Row
dbCur = dbCon.cursor()

pyplot.rc('font', family="NanumGothic")

with open('news.json', encoding="utf8") as f:
    newsJson = json.load(f)["news"]

nowNewses = []

@bot.command(name = "차트")
async def _chart(ctx):
    if stockChangeLoop.next_iteration == None:
        return
    time = datetime.datetime.now()
    embed=discord.Embed(title="주식 차트", description=f"주가 변동까지 {stockChangeLoop.next_iteration.timestamp() - time.timestamp(): .0f}초 남음", color=0x46e41b)
    dbCur.execute('SELECT * FROM stock_datas')
    result = dbCur.fetchall()
    up = 0
    down = 0
    for row in result:
        if row['nowPrice'] <= 500:
            embed.add_field(name=f"{row['stockName']} ({row['stockId']})", value=f":x: {row['nowPrice']:,d}원 (상장폐지)", inline=False)
            continue
        
        prevPrices = json.loads(row['prevPrice'])
        percent = "0%"
        symbol = ""
        if "prevPrices" in prevPrices:
            if (prevPrices['prevPrices'][1] != 0):
                percentNum = ((prevPrices['prevPrices'][0] / prevPrices['prevPrices'][1]) * 100) - 100
                if percentNum > 0:
                    up += 1
                    symbol = "<:_u:1187707241550331954>"
                elif percentNum < 0:
                    down += 1
                    symbol = "<:_d:1187707229793697862>"
                percent = f"{prevPrices['prevPrices'][0] - prevPrices['prevPrices'][1]}, {percentNum:.1f}%"
        
        embed.add_field(name=f"{row['stockName']} ({row['stockId']})", value=f"{symbol} {row['nowPrice']:,d}원 ({percent})", inline=False)
    
    if (up < down):
        embed.color = 0xe11f09
    elif (up == down):
        embed.color = 0x8a1be4

    embed.set_footer(text=time.strftime("%Y-%m-%d %I:%M %p"))
    await ctx.reply(embed=embed)

@bot.command(name = "변동")
async def _change(ctx, arg1: int = 1):
    for i in range(0, arg1):
        await stockChange()

@bot.command(name = "그래프")
async def _graph(ctx, *args):
    dbCur.execute('SELECT * FROM stock_datas')
    result = dbCur.fetchall()

    for row in result:
        if (row['nowPrice'] > 500):
            if len(args) == 0 or row['stockName'] in args or row['stockId'] in args:
                prevPrices = json.loads(row['prevPrice'])
                pyplot.plot(list(reversed(["현재", "3분 전", "6분 전", "9분 전", "12분 전", "15분 전", "18분 전", "21분 전", "24분 전", "27분 전"])), list(reversed(prevPrices['prevPrices'])), marker='o', label=row['stockName'])

    pyplot.legend(loc='center left', bbox_to_anchor=(1, 0.5))
    pyplot.xlabel('시간')
    pyplot.xticks(rotation=45)
    pyplot.ylabel('주가')
    pyplot.grid(linestyle='--')
    pyplot.title('주식 그래프', fontsize=30)
    pyplot.tight_layout()
    pyplot.savefig('savedGraph.png')
    pyplot.close()
    await ctx.reply(file=discord.File('savedGraph.png'))

@bot.command(name = "초기화")
async def _reset(ctx):
    dbCur.execute("UPDATE stock_datas SET nowPrice = 10000, prevPrice = '{}'")
    dbCur.execute("DELETE FROM user_datas")
    dbCon.commit()
    await ctx.reply("> 초기화 되었습니다.")

@tasks.loop(minutes=3)
async def stockChangeLoop():
    await stockChange()

async def stockChange():
    random.seed(datetime.datetime.now().timestamp())
    dbCur.execute('SELECT * FROM stock_datas')
    result = dbCur.fetchall()
    for row in result:
        price = row['nowPrice']
        prev = price
        if price > 500:
            condition = row['condition']
            if condition >= 1:
                price = random.randint(price, price + int(price * 0.25))
            elif condition < 0:
                price = random.randint(price - int(price * 0.25), price)
            else:
                price = random.randint(price - int(price * 0.25), price + int(price * 0.25))
            
            prevPrices = json.loads(row['prevPrice'])
            if not "prevPrices" in prevPrices:
                prevPrices = {"prevPrices": [price, prev, 0, 0, 0, 0, 0, 0, 0, 0]}
            else:
                prevPrices['prevPrices'].insert(0, price)
                prevPrices['prevPrices'].pop()
            dbCur.execute(f"UPDATE stock_datas SET nowPrice = {price}, prevPrice = '{json.dumps(prevPrices)}', condition = 0 WHERE stockId = '{row['stockId']}'")

    global nowNewses
    nowNewses = []
    selectedStocks = []
    while len(nowNewses) < 3:
        choicedNews = random.choice(newsJson)
        stockId = choicedNews['stockId']
        chociedNewsStockPrice = next((row['nowPrice'] for row in result if row['stockId'] == stockId), None)
        if chociedNewsStockPrice > 500 and choicedNews not in nowNewses and choicedNews['stockId'] not in selectedStocks:
            print(choicedNews)
            nowNewses.append(choicedNews)
            selectedStocks.append(stockId)

    for nowNews in nowNewses:
        dbCur.execute(f"UPDATE stock_datas SET condition={nowNews['condition']} WHERE stockId = '{nowNews['stockId']}'")

    dbCon.commit()
    time = datetime.datetime.now()
    embed=discord.Embed(title="주가가 변동되었습니다.", description=time.strftime("%Y-%m-%d %I:%M %p"), color=0x2483ff)
    await bot.get_channel(int(os.getenv("STOCK_CHANGE_NOTICE_CHANNEL"))).send(embed=embed)

@bot.command(name = "가입")
async def _register(ctx):
    dbCur.execute(f"SELECT * FROM user_datas WHERE userId = '{ctx.author.id}'")
    userData = dbCur.fetchone()
    if userData == None:
        dbCur.execute(f"INSERT INTO user_datas VALUES ('{ctx.author.id}', 50000, '{{}}')")
        dbCon.commit()
        embed=discord.Embed(title=":white_check_mark: 가입 완료", description="50,000원이 지급되었습니다.", color=0x209400)
        await ctx.reply(embed=embed)
    else:
        embed=discord.Embed(title=":warning: 이미 가입되어 있는 사용자 입니다.", color=0x940000)
        await ctx.reply(embed=embed)

@bot.command(name="지갑")
async def _wallet(ctx):
    dbCur.execute(f"SELECT * FROM user_datas WHERE userId = '{ctx.author.id}'")
    userData = dbCur.fetchone()

    if userData is None:
        embed = discord.Embed(title=":warning: 가입이 되어있지 않은 사용자 입니다.", description="!가입 명령어를 통해 가입을 먼저 해주세요.", color=0x940000)
        await ctx.reply(embed=embed)
        return

    userStockDatas = json.loads(userData['stockDatas'])

    embed = discord.Embed(title="지갑", description=f"보유 금액: {int(userData['money']):,d}원", color=0x949494)

    for stockId in userStockDatas:
        if userStockDatas[stockId]['amount'] <= 0:
            continue

        dbCur.execute(f"SELECT * FROM stock_datas WHERE stockId = '{stockId}'")
        stockData = dbCur.fetchone()

        symbol = ""
        revenue = stockData['nowPrice'] * userStockDatas[stockId]['amount'] - userStockDatas[stockId]['price']
        revenuePercent = (stockData['nowPrice'] * userStockDatas[stockId]['amount'] / userStockDatas[stockId]['price']) * 100 - 100
        if revenue > 0:
            symbol = "+"

        embed.add_field(name=f"{stockData['stockName']} ({stockData['stockId']})", value=f"{userStockDatas[stockId]['amount']}주 ({symbol}{int(revenue):,d}원, {symbol}{revenuePercent:.1f}%)", inline=False)

    await ctx.reply(embed=embed)

@bot.command(name = "매수")
async def _buy(ctx, arg1: str, arg2: str = "1"):
    dbCur.execute(f"SELECT * FROM user_datas WHERE userId = '{ctx.author.id}'")
    userData = dbCur.fetchone()

    if userData == None:
        embed=discord.Embed(title=":warning: 가입이 되어있지 않은 사용자 입니다.", description="!가입 명령어를 통해 가입을 먼저 해주세요.", color=0x940000)
        await ctx.reply(embed=embed)
        return

    dbCur.execute(f"SELECT * FROM stock_datas WHERE stockId = '{arg1}' OR stockName = '{arg1}'")
    stockData = dbCur.fetchone()
    if stockData == None:
        embed=discord.Embed(title=":warning: 존재하지 않는 종목 입니다.", color=0x940000)
        await ctx.reply(embed=embed)
        return
    
    if stockData['nowPrice'] <= 500:
        embed=discord.Embed(title=":warning: 상장폐지 된 종목입니다.", color=0x940000)
        await ctx.reply(embed=embed)
        return

    if arg2 in ["전부", "모두", "all", "올"]:
        arg2 = int(userData['money'] / stockData['nowPrice'])
    else:
        arg2 = int(arg2)
        if arg2 < 1:
            embed=discord.Embed(title=":warning: 개수는 1 이상 이여야 합니다.", color=0x940000)
            await ctx.reply(embed=embed)
            return
    
    stockId = stockData['stockId']
    
    price = stockData['nowPrice'] * arg2
    if (userData['money'] - price) < 0:
        embed=discord.Embed(title=f":warning: {price - userData['money']:,d}원이 부족합니다.", color=0x940000)
        await ctx.send(embed=embed)
        return
    
    userStockDatas = json.loads(userData['stockDatas'])
    if stockId in userStockDatas:
        userStockDatas[stockId]['amount'] += arg2
        userStockDatas[stockId]['price'] += price
    else:
        userStockDatas[stockId] = {"amount": arg2, "price": price}
    dbCur.execute(f"UPDATE user_datas SET money = {userData['money'] - price}, stockDatas = '{json.dumps(userStockDatas)}' WHERE userId = '{ctx.author.id}'")
    dbCon.commit()

    embed=discord.Embed(title="주식 매수 완료", description=f"**{stockData['stockName']}** 주식 **{arg2}**주를 **{price:,d}원**에 매수했습니다.", color=0x5ccc69)
    embed.set_footer(text=f"{stockData['stockName']} {userStockDatas[stockId]['amount']}주 보유 | 잔액: {userData['money'] - price:,d}")
    await ctx.reply(embed=embed)

@bot.command(name = "매도")
async def _sell(ctx, arg1: str, arg2: str = "1"):
    dbCur.execute(f"SELECT * FROM user_datas WHERE userId = '{ctx.author.id}'")
    userData = dbCur.fetchone()

    if userData == None:
        embed=discord.Embed(title=":warning: 가입이 되어있지 않은 사용자 입니다.", description="!가입 명령어를 통해 가입을 먼저 해주세요.", color=0x940000)
        await ctx.reply(embed=embed)
        return

    dbCur.execute(f"SELECT * FROM stock_datas WHERE stockId = '{arg1}' OR stockName = '{arg1}'")
    stockData = dbCur.fetchone()
    if stockData == None:
        embed=discord.Embed(title=":warning: 존재하지 않는 종목 입니다.", color=0x940000)
        await ctx.reply(embed=embed)
        return
    
    if stockData['nowPrice'] <= 500:
        embed=discord.Embed(title=":warning: 상장폐지 된 종목입니다.", color=0x940000)
        await ctx.reply(embed=embed)
        return

    stockId = stockData['stockId']
    
    userStockDatas = json.loads(userData['stockDatas'])
    if not stockId in userStockDatas:
        embed=discord.Embed(title=":warning: 보유하고 있지 않은 종목 입니다.", color=0x940000)
        await ctx.reply(embed=embed)
        return
    
    if userStockDatas[stockId]['amount'] <= 0:
        embed=discord.Embed(title=":warning: 보유하고 있지 않은 종목 입니다.", color=0x940000)
        await ctx.reply(embed=embed)
        return
    
    if arg2 in ["전부", "모두", "all", "올"]:
        arg2 = userStockDatas[stockId]['amount']
    else:
        arg2 = int(arg2)
        if arg2 < 1:
            embed=discord.Embed(title=":warning: 개수는 1 이상 이여야 합니다.", color=0x940000)
            await ctx.reply(embed=embed)
            return
    
    price = stockData['nowPrice'] * arg2

    avg = userStockDatas[stockId]['price'] / userStockDatas[stockId]['amount']
    userStockDatas[stockId]['amount'] -= arg2
    userStockDatas[stockId]['price'] -= avg * arg2

    dbCur.execute(f"UPDATE user_datas SET money = {userData['money'] + price}, stockDatas = '{json.dumps(userStockDatas)}' WHERE userId = '{ctx.author.id}'")
    dbCon.commit()

    embed=discord.Embed(title="주식 매도 완료", description=f"**{stockData['stockName']}** 주식 **{arg2}**주를 **{price:,d}원**에 매도했습니다.", color=0x5ccc69)
    embed.set_footer(text=f"{stockData['stockName']} {userStockDatas[stockId]['amount']}주 보유 | 잔액: {userData['money'] + price:,d}")
    await ctx.reply(embed=embed)

@bot.command(name = "뉴스")
async def _news(ctx):
    embed=discord.Embed(title="뉴스 기사", color=0xf6e313)
    for news in nowNewses:
        embed.add_field(name="> " + news['content'], value="", inline=False)
    await ctx.reply(embed=embed)

@bot.event
async def on_ready():
    print('# BOT: ON')

    stockChangeLoop.start()

bot.run(os.getenv('DISCORD_TOKEN'))