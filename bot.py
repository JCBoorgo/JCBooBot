import os
import json
import requests
from twitchio.ext import commands
# Note to a less lazy future self: YO DUDE JUST USE GOOGLE DRIVE TO DISPLAY STATS

# TO RUN THE BOT: do "pipenv run python bot.py" in cmd (when in this directory, of course)

strat = "PrayAgainstMe"

test = False
test_tour_id = "tournament_1597813278849"
tournament_data = None
# Can the current strategy compute things right after poking the API?
pre_compute_strat = True
strategy_data = {}
balance = 100
intended_bet = "0"
current_match = "None"
current_teams = ["no one", "no one"]
current_bet = [0, "no one"]
current_pot = [0, 0]
correct_bets_this_boot = 0
wrong_bets_this_boot = 0

bot = commands.Bot(
    # set up the bot
    irc_token=os.environ['TMI_TOKEN'],
    client_id=os.environ['CLIENT_ID'],
    nick=os.environ['BOT_NICK'],
    prefix=os.environ['BOT_PREFIX'],
    initial_channels=[os.environ['CHANNEL']]
)

# Never called if pre_compute_strat is False
def pre_compute_strategy():
    global strategy_data
    # PrayAgainstMe strat
    total_faiths = []
    highest_faiths = []
    lowest_faiths = []
    for team in range(len(tournament_data["teams"])):
        faith = 0
        highest = 0
        lowest = 200
        for unit in tournament_data["teams"][team]["units"]:
            unit_faith = int(unit["faith"])
            faith += unit_faith
            if unit_faith > highest:
                highest = unit_faith
            if unit_faith < lowest:
                lowest = unit_faith
        total_faiths.append(faith)
        highest_faiths.append(highest)
        lowest_faiths.append(lowest)
    strategy_data["total_faiths"] = total_faiths
    strategy_data["highest_faiths"] = highest_faiths
    strategy_data["lowest_faiths"] = lowest_faiths


def fetch_tournament():
    global tournament_data
    if not test:
        tournament_data = requests.get("https://mustad.io/api/tournaments/latest").json()
    else:
        with open("Tournaments/" + test_tour_id + ".json", "r") as f:
            tournament_data = json.load(f)
    tournament_number = tournament_data["id"]
    for team in range(len(tournament_data["teams"])):
        tournament_data["teams"][team].pop("tournamentId", None)
        for unit in range(len(tournament_data["teams"][team]["units"])):
            tournament_data["teams"][team]["units"][unit].pop("tournamentId", None)
    if pre_compute_strat:
        pre_compute_strategy()
    with open("Tournaments/" + tournament_number + ".json", "w") as dest_file:
        json.dump(tournament_data, dest_file, indent=2)

def convert_team_to_number(team_name):
    if team_name == "red":
        return 0
    if team_name == "blue":
        return 1
    if team_name == "green":
        return 2
    if team_name == "yellow":
        return 3
    if team_name == "white":
        return 4
    if team_name == "black":
        return 5
    if team_name == "purple":
        return 6
    if team_name == "brown":
        return 7
    if team_name == "champion":
        return 8

def find_match_in_bracket(team_left, team_right):
    num_left = convert_team_to_number(team_left)
    num_right = convert_team_to_number(team_right)
    if num_right == 8:
        return "Champ"
    if num_left == 0 and num_right == 1:
        return "Quarter_1"
    if num_left == 2 and num_right == 3:
        return "Quarter_2"
    if num_left == 4 and num_right == 5:
        return "Quarter_3"
    if num_left == 6 and num_right == 7:
        return "Quarter_4"
    if 0 <= num_left <= 1 and 2 <= num_right <= 3:
        return "Semi_1"
    if 4 <= num_left <= 5 and 6 <= num_right <= 7:
        return "Semi_2"
    if 0 <= num_left <= 3 and 4 <= num_right <= 7:
        return "Finals"

def send_bet(message):
    global intended_bet
    global current_match
    global current_teams
    # Find team color words ([4] and [6])
    words = message.split(' ')
    left_word = words[4]
    right_word = words[6][:-1] #That removes the dot
    team_left = convert_team_to_number(left_word)
    team_right = convert_team_to_number(right_word)
    current_match = find_match_in_bracket(left_word, right_word)
    current_teams[0] = left_word
    current_teams[1] = right_word
    if test:
        print(left_word + " vs " + right_word)
    # Poke the API if it's Red vs Blue because new tournament
    if team_left == 0 and team_right == 1:
        fetch_tournament()
    # PrayAgainstMe strat
    faith_left = strategy_data["total_faiths"][team_left]
    faith_right = strategy_data["total_faiths"][team_right]
    if faith_left <= faith_right:
        winning_team = team_left
        winning_word = left_word
        losing_team = team_right
    else:
        winning_team = team_right
        winning_word = right_word
        losing_team = team_left
    percentage = strategy_data["highest_faiths"][winning_team] - strategy_data["lowest_faiths"][losing_team]
    intended_bet = str(percentage) + "%"
    print(intended_bet)
    # Adjust the bet
    # Don't bet under 10%
    if percentage < 10:
        percentage = 10
    # !allin if the bet would take us to 100 or under
    if balance * (100 - percentage) / 100 < 100:
        betting_message = "!allin " + winning_word
    else:
        betting_message = "!bet " + str(percentage) + "% " + winning_word
    print(betting_message)
    if not test:
        # Return to be sent
        return betting_message

def update_balance(message):
    global balance
    words = message.split(' ')
    start_of_our_message = words.index("jcboobot,")
    balance = int(words[start_of_our_message + 5][:-1].replace(",", ""))
    print("Balance is " + str(balance) + "G")

def update_current_bet(message):
    global current_bet
    words = message.split(' ') #[4][:-1] for amount, [6][:-1] for team if bot name is 0
    start_of_our_message = words.index("jcboobot,")
    current_bet[0] = int(words[start_of_our_message + 4][:-1].replace(",", ""))
    current_bet[1] = words[start_of_our_message + 6][:-1]

def log_result(message):
    global correct_bets_this_boot
    global wrong_bets_this_boot
    tournament_id = tournament_data["id"]
    if not os.path.isfile("Results/" + tournament_id + ".json"):
        results = {}
    else:
        with open("Results/" + tournament_id + ".json", "r") as f:
            results = json.load(f)
    words = message.split(' ')
    winner = words[1]
    if winner == current_bet[1]:
        correct_bets_this_boot += 1
    elif current_bet[1] != "no one":
        wrong_bets_this_boot += 1
    if not current_match: # that would mean it's None, thus it wasn't there at the beginning
        return
    results[current_match] = {}
    results[current_match]["strat_used"] = strat
    results[current_match]["left_team"] = current_teams[0]
    results[current_match]["right_team"] = current_teams[1]
    results[current_match]["winner"] = winner
    results[current_match]["strat_bet_amount"] = current_bet[0]
    results[current_match]["strat_bet_team"] = current_bet[1]
    results[current_match]["strat_intended_bet"] = intended_bet
    results[current_match]["left_bets"] = current_pot[0]
    results[current_match]["right_bets"] = current_pot[1]
    with open("Results/" + tournament_id + ".json", "w") as dest_file:
        json.dump(results, dest_file, indent=2)

def check_pot(message):
    global current_pot
    words = message.split(' ')
    left_bets = int(words[10][:-2].replace(",", ""))
    right_bets = int(words[16][:-4].replace(",", ""))
    current_pot[0] = left_bets
    current_pot[1] = right_bets

@bot.event
async def event_ready():
    # When the bot comes online
    print(f"{os.environ['BOT_NICK']} is online!")
    ws = bot._ws  # this is only needed to send messages within event_ready
    fetch_tournament()
    await ws.send_privmsg(os.environ['CHANNEL'], f"!balance")
    # TESTING PURPOSES
    if test:
        print(strategy_data)

@bot.event
async def event_message(ctx):
    # Runs every time a message is sent in chat.
    # Ignore ourselves
    if ctx.author.name.lower() == os.environ['BOT_NICK'].lower():
        return
    # That handles all commands (probably won't have any, but eh)
    await bot.handle_commands(ctx)
    # Check if the FFTB bot sent something
    if ctx.author.name.lower() == "fftbattleground":
        fft_message = ctx.content.lower()
        if "jcboobot, your bettable" in fft_message:
            update_balance(fft_message)
        if "jcboobot, your bet is" in fft_message:
            update_current_bet(fft_message)
        if "betting is open" in fft_message:
            betting = send_bet(fft_message)
            if betting:
                await ctx.channel.send(betting)
        if "was victorious" in fft_message:
            log_result(fft_message)
            await ctx.channel.send("!balance")
        if "betting is closed" in fft_message:
            check_pot(fft_message)
            if not test:
                await ctx.channel.send("!bet")
    # User interaction things
    if "hey jcboobot, strat" in ctx.content.lower():
        await ctx.channel.send("PrayAgainstMe strat. Bet on team with the lowest total faith.")
    if "hey jcboobot, stats" in ctx.content.lower():
        await ctx.channel.send("Won " + str(correct_bets_this_boot) + " bets so far, lost " + str(wrong_bets_this_boot) + " bets")
    # Line below just replies to everything, do not do that
    # await ctx.channel.send(ctx.content)

# Command example
#@bot.command(name="willneverhappen")
#async def thatwonthappenever(ctx):
#    await ctx.send("Somehow it happened")

if __name__ == "__main__":
    bot.run()
