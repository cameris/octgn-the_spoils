from operator import itemgetter
from math import copysign

#---------------------------------------------------------------------------
# Constants
#---------------------------------------------------------------------------

phases = [
	'It is currently in the Pre-game Setup Phase',
	"{} uses their RESTORE Rule",
	"{} uses their DEVELOP Rule",
	"It is now {}'s ATTACK Phase",
	"It is now {}'s DEPLETE ATTACKERS Step",
	"It is now {}'s TACTIC and ABILITY Step",
	"It is now {}'s CHOOSE BLOCKING PARTY Step",
	"It is now {}'s RESOLVE BATTLE/SPEED Phase",
	"It is now {}'s TACTIC and ABILITY Step",
	"It is now {}'s ASSIGN DAMAGE(Highest Speed Group) Step",
	"It is now {}'s TACTIC and ABILITY Step",
	"It is now {}'s DAMAGE FOR SPEED GROUP INFLICTED Step",
	"It is now {}'s Repeat Resolve Damage Step/Blockers Deplete At End of Last Battle",
	"It is now {}'s END Step"]

ActivateColor = "#ffffff"
AttackColor = "#ff0000"
NSOTColor = "#ff8800"
BlockColor = "#0000ff"

token_marker = ("Token", "7e9610d4-c06d-437d-a5e6-100000000001")
locdmg_marker = ("Location Damage", "7e9610d4-c06d-437d-a5e6-100000000002")
dont_restore_marker = ("Don't Restore", "7e9610d4-c06d-437d-a5e6-100000000007")

STD_MICROMAJIG_GUID = "7e9610d4-c06d-437d-a5e6-000000000028"

CURRENT_LAYOUT_VERSION = "0.9"
DEFAULT_LAYOUT= "[['tok','chr','itm'],['res','fac','loc'],['oog']]"
DEFAULT_LAYOUT_SPACER = "{'card': 6, 'group': 40, 'same': 15, 'resource': 22, 'row': 10, 'attach_x': 15, 'attach_y': 15}"
DEFAULT_LAYOUT_RES_ATTACH_LEFT = "True"

INITIAL_ROW_OFFSET = 50

CARD_HEIGHT = 88
CARD_WIDTH = 63

BEING_PLAYED_X = 25
BEING_PLAYED_Y = 6

PLAYER_SPACER = 70

#---------------------------------------------------------------------------
# Global variables
#---------------------------------------------------------------------------

phaseIdx = 0
factionid = None
starting_roll = { 'max': 0, 'player': [], 'count': 0 }
question = ''
inplay_since_SOT = []

#---------------------------------------------------------------------------
# Table group actions
#---------------------------------------------------------------------------

def scoop(group, x = 0, y = 0):
	mute()
	if not confirm("Are you sure you want to scoop?"): return
	me.Influence = 25
	me.Obsession = 0
	me.Greed = 0
	me.Elitism = 0
	me.Deception = 0
	me.Rage = 0
	me.Staple = 0
	myCards = (card for card in table
				if card.owner == me)
	for card in myCards: 
		card.moveTo(me.piles['draw deck'])
	Library = me.piles['draw deck']
	for c in me.piles['Discard pile']: c.moveTo(Library)
	for c in me.hand: c.moveTo(Library)
	exile = me.piles['Out of Game']
	for c in exile: c.moveTo(Library)
	notify("{} scoops.".format(me))

def showCurrentPhase(group, x = 0, y = 0):
	if me.isActivePlayer:
		notify(phases[phaseIdx].format(me))
	else:
		active_players = eval(getGlobalVariable("seating_order"))
		for pid in active_players:
			if Player(pid).isActivePlayer:
				remoteCall(Player(pid), "showCurrentPhase", [table])

def nextPhase(group, x = 0, y = 0):
	#TODO: maybe remove this function, since spoils has no ordered gameflow?
	global phaseIdx
	if not confirm_my_turn():
		return

	phaseIdx += 1
	showCurrentPhase(group)

def goToRestore(group, x = 0, y = 0):
	global phaseIdx
	global factionid
	if not confirm_my_turn():
		return

	phaseIdx = 1
	mute()
	myCards = (card for card in table
				if card.controller == me
				and not has_dont_restore_marker(card))
	for card in myCards: 
		card.orientation &= ~Rot90

	attached = eval(getGlobalVariable("attached"))

	if attached.get(factionid):
		attached.pop(factionid)
	setGlobalVariable("attached", str(attached))

	reposition_cards(me)
	notify("{} uses their RESTORE Rule".format(me))

def goToDevelopment(group, x = 0, y = 0):
	global phaseIdx
	if not confirm_my_turn():
		return
	 
	phaseIdx = 2
	showCurrentPhase(group)

def goToAttack(group, x = 0, y = 0):
	global phaseIdx
	if not confirm_my_turn():
		return

	phaseIdx = 3
	showCurrentPhase(group)

def goToResolve(group, x = 0, y = 0):
	global phaseIdx
	if not confirm_my_turn():
		return

	phaseIdx = 7
	showCurrentPhase(group)

def goToEnd(group, x = 0, y = 0):
	global phaseIdx
	if not confirm_my_turn():
		return

	declared_eot = eval(getGlobalVariable("response_stack"))
	declared_eot = list(item for item in declared_eot if item['action'] == 'eot')
	if not declared_eot:
		phaseIdx = 13
		showCurrentPhase(group)
		trigger_response(me, None, 'eot')

def roll6(group, x = 0, y = 0):
	mute()
	n = rnd(1, 6)
	notify("{} rolls {} on a 6-sided die.".format(me, n))

def roll20(group, x = 0, y = 0):
	mute()
	n = rnd(1, 20)
	notify("{} rolls {} on a 20-sided die.".format(me, n))

def flipCoin(group, x = 0, y = 0):
	mute()
	n = rnd(1, 2)
	if n == 1:
		notify("{} flips heads.".format(me))
	else:
		notify("{} flips tails.".format(me))

def micromajig(group, x = 0, y = 0):
	table.create(STD_MICROMAJIG_GUID, x, y)
	reposition_cards(me)

def micromajig_menu(group, x = 0, y = 0):
	card, quantity = askCard({"Card Number": "Token"}, "and")
	if quantity == 0: return
	table.create(card, x, y, quantity)
	reposition_cards(me)

def clearAll(group, x = 0, y = 0):
	notify("{} clears all cards.".format(me))
	for card in group:
		card.target(False)
		if card.controller == me and card.highlight in [AttackColor, ActivateColor, BlockColor]:
			card.highlight = None

#---------------------------------------------------------------------------
# Table card actions
#---------------------------------------------------------------------------

def default_action(cards, x = 0, y = 0): # {{{
	mute()
	non_res = list(card for card in cards if card.type.lower() != 'resource' and card.isFaceUp == True)
	resources = list(card for card in cards if card.type.lower() == 'resource' or card.isFaceUp == False)
	if len(non_res):
		deplete(non_res)
	if len(resources):
		attach_to_faction(resources)
	# }}}

def deplete(cards, x = 0, y = 0): # {{{
	mute()
	global factionid

	for card in cards:
		card.orientation ^= Rot90
		if card.orientation & Rot90 == Rot90:
			notify('{} depletes {}'.format(me, card))
		else:
			card.highlight = None
			notify('{} restores {}'.format(me, card))
	reposition_cards(me)
	# }}}

def attach_to_faction(cards, x = 0, y = 0): # {{{
	mute()
	global factionid
	
	for card in cards:
		attached = eval(getGlobalVariable("attached"))

		# dont do out of game cards
		if has_oog_marker(card):
			continue

		if card._id in attached.get(factionid,[]):
			attached[factionid].remove(card._id)
			notify('{} detaches {} from Faction'.format(me, card))
		else:
			if attached.get(factionid):
				attached[factionid].append(card._id)
			else:
				attached[factionid] = [card._id]
			notify('{} attaches {} to Faction'.format(me, card))
		setGlobalVariable("attached", str(attached))
	reposition_cards(me)
	# }}}

def use_ability(cards, x = 0, y = 0): # {{{
	if len(cards) > 1:
		whisper("multiple cards selected, \"use ability\" only works on single cards")
		return
	card = cards[0]
	trigger_response(me, card, 'ability')
	# }}}

def attack(cards, x = 0, y = 0): # {{{
	mute()
	for card in cards:
		card.orientation |= Rot90
		card.highlight = AttackColor
		notify('{} attacks with {}'.format(me, card))
	reposition_cards(me)
	# }}}

def block(card, x = 0, y = 0):
	card.highlight = BlockColor
	notify('{} blocks with {}'.format(me, card))

def add_marker(cards, x = 0, y = 0):
	mute()
	marker, quantity = askMarker()
	if quantity == 0: return
	for c in cards:
		c.markers[marker] += quantity
		notify("{} adds {} {} marker to {}.".format(me, quantity, marker[0], c))

def add_token(card, x = 0, y = 0): # {{{
	mute()
	notify("{} adds a token to {}.".format(me, card))
	card.markers[token_marker] += 1
	# }}}

def remove_token(card, x = 0, y = 0): # {{{
	mute()
	notify("{} removes a token to {}.".format(me, card))
	card.markers[token_marker] -= 1
	# }}}

def add_loc_dmg(card, x = 0, y = 0): # {{{
	mute()
	notify("{} adds a location damage marker to {}.".format(me, card))
	card.markers[locdmg_marker] += 1
	# }}}

def remove_loc_dmg(card, x = 0, y = 0): # {{{
	mute()
	notify("{} removes a location damage marker from {}.".format(me, card))
	card.markers[locdmg_marker] -= 1
	# }}}

def flip_up(cards, x = 0, y = 0): # {{{
	mute()
	global factionid
	global inplay_since_SOT

	faceup_count = 0
	for card in cards:
		if card.isFaceUp:
			faceup_count += 1

	if len(cards) == faceup_count: # flip down selected cards
		attached = eval(getGlobalVariable("attached"))
		changed_attached = False

		for card in cards:
			# detach card if it was attached
			for targetid in attached:
				if card._id in attached.get(targetid,[]):
						attached[targetid].remove(card._id)
						changed_attached = True

			# remove all markers
			for marker in card.markers:
				card.markers[marker] = 0

			card.isFaceUp = False
			card.orientation = Rot0
			notify("{} flips down {}.".format(me, card))
			card.peek()

		if changed_attached:
			setGlobalVariable("attached", str(attached))
				
		reposition_cards(me)

	elif len(cards) == 1 and faceup_count == 0: # flip up single card
		card = cards[0]
		attached = eval(getGlobalVariable("attached"))

		# remove from faction attached list
		if card._id in attached.get(factionid,[]):
			attached[factionid].remove(card._id)
			setGlobalVariable("attached", str(attached))

		# remove from inplay list
		if inplay_since_SOT.count(card._id):
			inplay_since_SOT.remove(card._id)

		# remove all markers
		for marker in card.markers:
			card.markers[marker] = 0

		card.isFaceUp = True
		notify("{} flips up {}.".format(me, card))
		trigger_response(me, card, 'play')

	elif len(cards) > 1 and faceup_count == 0: # flip up only wroks on single cards
		whisper("multiple cards selected, \"flip up\" only works on single cards")
	
	else:
		whisper("select either one facedown card or multiple faceup cards")
	# }}}

def reveal(card, x = 0, y = 0):
	mute()
	if card.isFaceUp:
		notify("{} hides {}.".format(me, card))
		card.isFaceUp = False
		card.peek()
	else:
		card.isFaceUp = True
		notify("{} reveals {}.".format(me, card))

def clear(card, x = 0, y = 0):
	mute()

	notify("{} clears {}.".format(me, card))
	card.highlight = None
	card.target(False)

def toggle_dont_restore(card, x = 0, y = 0): # {{{
	mute()

	if card.markers[dont_restore_marker] == 0:
		card.markers[dont_restore_marker] = 1
	else:
		card.markers[dont_restore_marker] = 0
	# }}}


#---------------------------
# movement actions
#---------------------------

def destroy(card, x = 0, y = 0):
	mute()
	src = card.group
	fromText = " from play" if src == table else " from their " + src.name
	notify("{} destroys {}{}.".format(me, card, fromText))
	card.moveTo(card.owner.piles['Discard pile'])

def removefromgame(card, x = 0, y = 0):
	mute()
	notify("{} removes {} from game.".format(me, card))
	card.moveTo(card.owner.piles['out of game'])

def movetodrawdeck(card, x = 0, y = 0):
	mute()
	if card.owner == me:
		notify("{} moves {} to top of draw deck.".format(me, card))
		card.moveTo(me.piles['draw deck'])
	else:
		whisper("You do not own {}".format(card))

def tohand(card, x = 0, y = 0):
	mute()
	if card.owner == me:
		src = card.group
		fromText = " from the table" if src == table else " from their " + src.name
		notify("{} returns {} to their hand{}.".format(me, card, fromText))
		card.moveTo(me.hand)
	else:
		whisper("You do not own {}".format(card))

def movetobottom(card, x = 0, y = 0):
	mute()
	if card.owner == me:
		notify("{} moves {} to bottom of draw deck.".format(me, card))
		card.moveToBottom(me.piles['draw deck'])
	else:
		whisper("You do not own {}".format(card))


#------------------------------------------------------------------------------
# Hand Actions
#------------------------------------------------------------------------------

def play(card, x = 0, y = 0):
	mute()
	src = card.group
	if card.type.lower() == 'resource':
		sign = -1 if me.hasInvertedTable() else 1
		card.moveToTable(-1*card.width()/2, -1*card.height()/2 + sign * BEING_PLAYED_Y)
		notify("{} plays {} from their {}.".format(me, card, src.name))
		reposition_cards(me)
	else:
		trigger_response(me, card, 'play')

def randomDiscard(group):
	mute()
	card = group.random()
	if card == None: return
	card.moveTo(me.piles['Discard pile'])
	notify("{} randomly discards {}.".format(me, card))

def discard(card, x = 0, y = 0):
	mute()
	card.moveTo(me.piles['Discard pile'])
	notify("{} discards {} from their hand.".format(me, card))

def removefromgame(card, x = 0, y = 0):
	mute()
	card.moveTo(me.piles['out of game'])
	notify("{} removes {} from game.".format(me, card))

def playresource(card, x = 0, y = 0):
	mute()
	sign = -1 if me.hasInvertedTable() else 1
	card.moveToTable(-1*card.width()/2, -1*card.height()/2 + sign * BEING_PLAYED_Y, True)
	card.peek()
	notify("{} plays resource card from their hand.".format(me))
	reposition_cards(me)

#------------------------------------------------------------------------------
# Pile Actions
#------------------------------------------------------------------------------

def draw(group, x = 0, y = 0):
	if len(group) == 0: return
	mute()
	group[0].moveTo(me.hand)
	notify("{} draws a card.".format(me))

def shuffle(group, x = 0, y = 0): # {{{
	group.shuffle()
	notify("{} shuffled his {}".format(me, group.name))
	# }}}

def drawMany(group, count = None): # {{{
	if len(group) == 0: return
	mute()
	if count == None: count = askInteger("Draw how many cards?", 0)
	if count > 0:
		for c in group.top(count): c.moveTo(me.hand)
		notify("{} draws {} cards.".format(me, count))
	# }}}

def destroyxcards(group, count = None): # {{{
	if len(group) == 0: return
	mute()
	if count == None: count = askInteger("Put how many cards into Discard pile?", 0)
	if count > 0:
		notify("{} puts {} card(s) from their {} into their Discard pile:".format(me, count, group.name))
		for c in group.top(count):
			c.moveTo(me.piles['Discard pile'])
			notify("{}".format(c))
	# }}}

def removexcards(group, count = None): # {{{
	if len(group) == 0: return
	mute()
	if count == None: count = askInteger("Remove how many cards from the game?", 0)
	if count > 0:
		notify("{} removes {} card(s) from their {} from the game:".format(me, count, group.name))
		for c in group.top(count):
			c.moveTo(me.piles['out of game'])
			notify("{}".format(c))
	# }}}

def playfacedown(card, x = 0, y = 0): # {{{
	mute()
	notify("{} plays card face-down from their {}.".format(me, card.group.name))
	card.moveToTable(0, 0, True)
	# }}}

def randomdraw(group): # {{{
	mute()
	card = group.random()
	if card == None: return
	notify("{} randomly draws a card from their {}.".format(me, group.name))
	card.moveTo(me.hand)
	# }}}

#------------------------------------------------------------------------------
# Events
#------------------------------------------------------------------------------

def on_move_card(player, card, fromgrp, togrp, oldindex, newindex, oldx, oldy, newx, newy, isscripted): # {{{
	global inplay_since_SOT
	if player == me:
		if fromgrp == table and togrp != table:
			attached = eval(getGlobalVariable("attached"))
			update_attached(attached)
			# remove from inplay list
			if inplay_since_SOT.count(card._id):
				inplay_since_SOT.remove(card._id)
	# }}}

def on_table_load(): # {{{
	mute()

	# check for changed layout version
	layout_version = getSetting("layout_version", "0.0")
	if layout_version != CURRENT_LAYOUT_VERSION:
		whisper("LAYOUT: new layout version detected, defaults loaded")
		setSetting("layout_version", CURRENT_LAYOUT_VERSION)
		setSetting("layout", DEFAULT_LAYOUT)
		setSetting("layout_spacer", DEFAULT_LAYOUT_SPACER)
		setSetting("layout_res_attach_left", DEFAULT_LAYOUT_RES_ATTACH_LEFT)
	
	# check for changes in game version
	# sorting key function for version string
	def version_tuple(v):
		return tuple(map(int, (v.split("."))))

	last_game_version = getSetting("last_game_version", "0")
	versions = sorted(changelog.keys(), key=version_tuple)
	for ver in versions:
		if version_tuple(last_game_version) < version_tuple(ver):
			log = changelog[ver]
			log = '\n\n>>> '.join(log)
			choice = confirm("Changes in {}:\n>>> {}\n\nShow next log?".format(ver, log))
			if choice == False:
				break
	setSetting("last_game_version", gameVersion)

	# set layout
	layout = eval(getSetting("layout", DEFAULT_LAYOUT))
	setGlobalVariable("layout_" + str(me._id), str(layout))
	spacer = eval(getSetting("layout_spacer", DEFAULT_LAYOUT_SPACER))
	setGlobalVariable("layout_spacer_" + str(me._id), str(spacer))
	res_attach_left = eval(getSetting("layout_res_attach_left", DEFAULT_LAYOUT_RES_ATTACH_LEFT))
	setGlobalVariable("layout_res_attach_left_" + str(me._id), str(res_attach_left))
	# }}}

def on_game_start(): # {{{
	mute()
	global starting_roll
	starting_roll = { 'max': 0, 'player': [], 'count': 0 }

	# reset starting player
	setGlobalVariable("starting_player", str(None))

	# init seating order
	if me._id == 1: # host decides
		active_players = getGlobalVariable("seating_order")
		if not active_players:
			if len(getPlayers()) > 2:
				change_seating_order(table)
			else:
				setGlobalVariable("seating_order", str(list(p._id for p in getPlayers())) )
	# }}}

def on_load_deck(player, groups): # {{{
	mute()
	global factionid
	global starting_roll

	# move faction and resources to table, shuffle deck
	if player == me:
		for card in me.hand:
			if card.type.lower() == 'faction':
				factionid = card._id
				card.moveToTable(0,0)
			elif card.type.lower() == 'resource' and card.subtype.lower() == 'staple':
				card.moveToTable(0,0,True)
				card.peek()
		reposition_cards(me)

		shuffle(me.piles['Draw deck'])

	# roll to get the starting player
	if me._id == 1:
		active_players = eval(getGlobalVariable("seating_order"))
		n = rnd(1, 20)
		notify("{} rolls {} on a 20-sided die.".format(player, n))
		starting_roll['count'] += 1
		if n > starting_roll['max']:
			starting_roll['max'] = n 
			starting_roll['player'] = [player]
		elif n == starting_roll['max']:
			starting_roll['player'].append(player)

		if starting_roll['count'] >= len(active_players):
			# reroll on draw
			while len(starting_roll['player']) > 1:
				maxcount = len(starting_roll['player'])
				rollers = starting_roll['player']
				starting_roll = { 'max': 0, 'player': [], 'count': 0 }

				for player in rollers:
					n = rnd(1, 20)
					notify("{} rolls {} on a 20-sided die.".format(player, n))
					starting_roll['count'] += 1
					if n > starting_roll['max']:
						starting_roll['max'] = n 
						starting_roll['player'] = [player]
					elif n == starting_roll['max']:
						starting_roll['player'].append(player)

			remoteCall(starting_roll['player'][0], "choose_starting_player", None)
	# }}}

def on_glob_var_change(name, oldval, newval): # {{{
	mute()
	# response system
	# stack: [{ 'pid': playerid, 'cid': cardid, 'did': dupeid, 'action': action, 'done': { playerid: bool, ... }}, ... ]
	# 	action:
	# 		'play' = playing a card
	# 		'ability' = using an ability
	# 		'eot' = end of turn
	if name == "response_stack": # {{{
		global question
		question = ''

		stack = eval(newval)
		active_players = eval(getGlobalVariable("seating_order"))
		if stack:
			card = Card(stack[-1]['cid']) if stack[-1]['cid'] else None
			dupe = Card(stack[-1]['did']) if stack[-1]['did'] else None
			player = Player(stack[-1]['pid'])

			if player._id == me._id: # player that triggered the response

				# do nothing if not everyone had time to respond
				if False in stack[-1]['done'].values():
					# get responding players
					resp_names = []
					resp_player = get_next_player(player, active_players)
					while resp_player != player:
						if stack[-1]['done'][resp_player._id] == False:
							resp_names.append(resp_player.name)
						resp_player = get_next_player(resp_player, active_players)

					whisper("RESPONSE: waiting for {}".format(', '.join(resp_names)))
					return

				# get next response
				resolve = stack.pop()
				setGlobalVariable("response_stack",str(stack))

				# resolve the actions
				if resolve['action'] == 'play':
					whisper("RESPONSE: resolve playing {}".format(card))
					if card.controller == me:
						reposition_cards(player)
					else:
						remoteCall(card.controller,"reposition_cards",[card.controller._id])

				elif resolve['action'] == 'ability':
					whisper("RESPONSE: resolve {}\'s ability".format(dupe))
					# destroy duplicate
					if dupe:
						dupe.moveTo(me.hand)
					card.highlight = None
					if resolve['fd']:
						card.isFaceUp = False

				elif resolve['action'] == 'eot':
					notify("RESPONSE: {} ends his turn".format(player))
					nextplayer = get_next_player(player, active_players)
					nextplayer.setActivePlayer()

				else:
					notify("DEBUG: RESPONSE: unknown action: \'{}\'".format(stack[-1]['action']))

			else: # responding player
				# ordered respond
				resp_player = get_next_player(player, active_players)
				while resp_player != player:
					if stack[-1]['done'][resp_player._id] == False:
						if resp_player != me:
							break

						# question player 
						question = 'response'
						if stack[-1]['action'] == 'play':
							whisper("RESPONSE: respond to {} being played?".format(card))

						elif stack[-1]['action'] == 'ability':
							whisper("RESPONSE: respond to {}\'s ability?".format(dupe))

						elif stack[-1]['action'] == 'eot':
							whisper("RESPONSE: respond to {}\'s End Of Turn?".format(player))

						else:
							notify("DEBUG: RESPONSE: unknown action: \'{}\'".format(stack[-1]['action']))

						break
					resp_player = get_next_player(resp_player, active_players)
		# }}}

	elif name == "starting_player":
		playerid = eval(newval)
		if playerid != None:
			fdres = list(c for c in table if c.controller == me and c.isFaceUp == False)
			for c in fdres:
				c.isFaceUp = True
	# }}}

def on_turn(player, turn): # {{{
	# update inplay list
	global inplay_since_SOT
	inplay_since_SOT = list(c._id for c in table if c.controller == me)
	for cid in inplay_since_SOT:
		Card(cid).highlight = None
	# }}}

def on_card_click(card, button, keys): # {{{
	if card.controller == me:
		if button == 0: # left click
			if 'Tab' in keys:
				use_ability([card])
			elif 'LeftAlt' in keys:
				if card.group == me.hand:
					playresource(card)
	# }}}

def answer_yes(group, x = 0, y = 0): # {{{
	global question
	if question == 'response':
		notify('RESPONSE: {} responds!'.format(me))
	else:
		notify("PAUSE: {} needs time to think".format(me))
	# }}}

def answer_no(group, x = 0, y = 0): # {{{
	mute()
	global question

	if question == 'response':
		notify('RESPONSE: {} doesn\'t respond!'.format(me))
		stack = eval(getGlobalVariable("response_stack"))
		if stack:
			stack[-1]['done'][me._id] = True
			setGlobalVariable("response_stack", str(stack))
		else:
			notify("DEBUG: ANSWER_NO: response_stack is empty")
	else:
		notify("CONTINUE: {} ready to continue".format(me))
	# }}}

def confirm_my_turn(): # {{{
	if me.isActivePlayer:
		return True
	return confirm("It's not your turn, still want to contine?") # }}}

#------------------------------------------------------------------------------
# Game settings
#------------------------------------------------------------------------------

def change_seating_order(group, x=0, y=0): # {{{
	allplayers = list(p for p in getPlayers())
	seating_order = []

	title = "Add an active player:"
	colors = list('#000000' for p in allplayers)
	choice = askChoice(title, list(p.name for p in allplayers), colors) 
	
	seating_order.append( allplayers.pop(choice-1) )

	while len(allplayers):
		title = "~eating order: {}\r\nwho sits left of {}?".format( ', '.join(list(p.name for p in seating_order)), seating_order[-1].name )
		choices = list(p.name for p in allplayers)
		choices.append("Rest are spectators")

		colors = list('#000000' for c in choices)
		colors[-1] = '#880000'
		choice = askChoice(title, choices, colors)

		if choice == len(choices):
			break
		else:
			seating_order.append( allplayers.pop(choice-1) )

		choices.pop()
	
	notify("{} has set the seating order to: {}".format(me, ', '.join(list(p.name for p in seating_order)) ))
	if len(allplayers):
		notify("spectators: {}".format( ', '.join(list(p.name for p in allplayers)) ))
	
	setGlobalVariable("seating_order", str(list(p._id for p in seating_order)) )
	# }}}

def choose_starting_player(args): # {{{
	active_players = eval(getGlobalVariable("seating_order"))

	if len(active_players) > 1:
		title = "You won the starting roll, select the starting player:"
		colors = list('#000000' for pid in active_players)
		choice = askChoice(title, list(Player(pid).name for pid in active_players), colors) 
	else:
		choice = 1

	notify("STARTING PLAYER: {} chooses {}".format(me, Player(active_players[choice-1])))
	setGlobalVariable("starting_player",str(active_players[choice-1]))
	Player(active_players[choice-1]).setActivePlayer()
# }}}

def change_layout(group, x=0, y=0): # {{{
	choice_map = { 'Characters':'chr', 'Items':'itm', 'Locations':'loc', 'Resources':'res', 
			'Faction':'fac', 'Out of Game':'oog', 'Tokens':'tok' }
	choices = choice_map.keys()
	result = []

	layout = get_layout(me)

	first = True
	currentrow = []
	while len(choices):
		if first:
			title = "Current Layout:\r\n"
			for row in layout:
				stringrow = []
				for id in row:
					for full, short in choice_map.items():
						if id == short:
							stringrow.append(full)
				title += ", ".join(stringrow)
				title += u' \u21b2\r\n'
			choices.append('Defaults')
		else:
			choices.append('New Row')

		colors = list('#000000' for item in choices)
		choice = askChoice('{}{}'.format(title,', '.join(currentrow)), choices, colors, customButtons=['Cancel'])

		if choice == len(choices):
			if first: # load defaults
				layout = eval(DEFAULT_LAYOUT)
				break
			else: # new row
				if len(currentrow):
					result.append(currentrow)
					title += u"{} \u21b2\r\n".format(', '.join(currentrow))
					currentrow = []
		elif choice == -1:
			return
		else:
			currentrow.append(choices.pop(choice-1))

		choices.pop()
		if first:
			first = False
			title = "Choosen Layout:\r\n"
		if len(choices) == 0:
			result.append(currentrow)
			layout = []
			for row in result:
				tmp = []
				for choice in row:
					tmp.append(choice_map[choice])
				layout.append(tmp)
	
	setSetting("layout", str(layout))
	setGlobalVariable("layout_" + str(me._id), str(layout))
	reposition_cards(me)
	# }}}

def change_spacer(group, x=0, y=0): # {{{
	choice_map = {'Cards':'card', 'Groups':'group', 'Grouped cards':'same', 'Resources':'resource', 'Rows':'row', 
			'Attached cards X':'attach_x', 'Attached cards Y':'attach_y'}
	choices = choice_map.keys()
	choices.sort()
	choices.append("Defaults")
	colors = list('#000000' for item in choices)

	spacer = get_layout_spacer(me)

	choice = True
	changed = False
	while choice > 0:
		choice = askChoice("Choose spacer setting:", choices, colors, customButtons=['Done'])

		if choice == len(choices):
			spacer = eval(DEFAULT_LAYOUT_SPACER)
			changed = True
		elif choice > 0:
			text = "{}:".format(choices[choice-1])
			current = spacer[ choice_map[ choices[choice-1] ]]
			new = askInteger(text, current)
			if new != current and new > 0:
				changed = True
				spacer[ choice_map[ choices[choice-1] ]] = new

	if changed:
		setSetting("layout_spacer", str(spacer))
		setGlobalVariable("layout_spacer_" + str(me._id), str(spacer))
		reposition_cards(me)
	# }}}

def change_res_attach(group, x=0, y=0): # {{{
	res_attach_left = get_layout_res_attach_left(me)
	if res_attach_left:
		whisper("LAYOUT: resources attach to the right of faction")
	else:
		whisper("LAYOUT: resources attach to the left of faction")
	res_attach_left = not res_attach_left
	setSetting("layout_res_attach_left", str(res_attach_left))
	setGlobalVariable("layout_res_attach_left_" + str(me._id), str(res_attach_left))
	reposition_cards(me)
	# }}}

#------------------------------------------------------------------------------
# Response
#------------------------------------------------------------------------------

def trigger_response(player, card, action): # {{{
	mute()
	stack = eval(getGlobalVariable("response_stack"))
	active_players = eval(getGlobalVariable("seating_order"))

	dupe = None
	facedown = False

	if stack:
		if stack[-1]['pid'] == player._id:
			confirm("It's not your time to respond!")
			return

		# calc coordinates and move card
		if action == 'play' or action == 'ability':
			being_played = list(item for item in stack if item['action'] == 'play' or item['action'] == 'ability')

			sign = -1 if player.hasInvertedTable() else 1
			y = -1 * card.height()/2 + sign * BEING_PLAYED_Y

			if being_played:
				if being_played[-1]['action'] == 'ability':
					x, tmp = Card(being_played[-1]['did']).position
				elif being_played[-1]['action'] == 'play':
					x, tmp = Card(being_played[-1]['cid']).position
				x += BEING_PLAYED_X
			else:
				x = -1 * card.width()/2

	else:
		# calc coordinates and move card
		if action == 'play' or action == 'ability':
			sign = -1 if player.hasInvertedTable() else 1
			y = -1 * card.height()/2 + sign * BEING_PLAYED_Y
			x = -1 * card.width()/2

	if action == 'play':
		src = card.group
		card.moveToTable(x, y)
		notify("{} plays {} from their {}.".format(me, card, src.name))

	elif action == 'ability':
		card.highlight = ActivateColor

		if not card.isFaceUp:
			facedown = True
			card.isFaceUp = True

		dupe = table.create(card.model, x, y)
		dupe.highlight = ActivateColor
		if card.group == table:
			notify("{} uses {}'s ability".format(me, dupe))
		else:
			notify("{} uses {}'s ability from their {}".format(me, dupe, card.group.name))


	# players that can respond
	resp_players = list(pid for pid in active_players if pid != player._id)
	done = {}

	# playing alone?
	if len(getPlayers()) > 1:
		for pid in resp_players:
			done[pid] = False
	else:
		done[player._id] = True

	# push to stack
	stack.append({'pid': player._id, 'cid': (card._id if card else None),
		'action': action, 'done': done, 'did': (dupe._id if dupe else None), 'fd': facedown })
	setGlobalVariable("response_stack", str(stack))
	# }}}

def end_response(group, x=0, y=0): # {{{
	global question
	question = ''
	notify("RESPONSE: manually ended by {}".format(me))
	setGlobalVariable("response_stack", str([]))
	# }}}

#------------------------------------------------------------------------------
# Getters
#------------------------------------------------------------------------------

def get_layout(player): # {{{
	layout = getGlobalVariable("layout_" + str(player._id))
	if layout:
		layout = eval(layout)
		if type(layout) == type(list()):
			return layout
	return eval(DEFAULT_LAYOUT) # }}}

def get_layout_spacer(player): # {{{
	spacer = getGlobalVariable("layout_spacer_" + str(player._id))
	if spacer:
		spacer = eval(spacer)
		if type(spacer) == type(dict()):
			return spacer
	return eval(DEFAULT_LAYOUT_SPACER) # }}}

def get_layout_res_attach_left(player): # {{{
	res_attach_left = getGlobalVariable("layout_res_attach_left_" + str(player._id))
	if res_attach_left:
		res_attach_left = eval(res_attach_left)
		if type(res_attach_left) == type(bool()):
			return res_attach_left
	return eval(DEFAULT_LAYOUT_RES_ATTACH_LEFT) # }}}

def get_next_player(curplayer, order): # {{{
	if type(curplayer) == type(int()):
		curplayer = Player(curplayer)
	index = order.index(curplayer._id)
	if index == (len(order)-1):
		index = 0
	else:
		index += 1
	return Player(order[index]) # }}}

def get_cards_on_stack(stack): # {{{
	ids_on_stack = list(item['cid'] for item in stack if item['action'] == 'play')
	ids_on_stack.extend(list(item['did'] for item in stack if item['action'] == 'ability'))
	return ids_on_stack # }}}

def has_oog_marker(card): # {{{
	oog_marker = False
	for marker in card.markers:
		if marker[0].lower()[:3] == 'oog':
			oog_marker = True
	return oog_marker # }}}

def has_dont_restore_marker(card): # {{{
	for marker in card.markers:
		if marker[1] == dont_restore_marker[1]:
			return True
	return False # }}}

#------------------------------------------------------------------------------
# Layout and placement
#------------------------------------------------------------------------------

def attach(card, x=0, y=0): # {{{
	attached = eval(getGlobalVariable("attached"))

	# get being played card ids
	being_played = eval(getGlobalVariable("response_stack"))
	being_played = get_cards_on_stack(being_played)
	
	# check if card is already attached to something, remove it from list
	for ids in attached.itervalues():
		if card._id in ids:
			ids.remove(card._id)

	# get target
	target = []
	for c in table:
		if c.targetedBy:
			if c.targetedBy == me:
				target.append(c)
			
	# attach card to target
	if len(target) == 1:
		target = target[0]
		if target._id == card._id:
			whisper("can't attach a card to itself")
			return
		target.target(False)
		if attached.get(target._id):
			attached[target._id].append(card._id)  
		else:
			attached[target._id] = [card._id]
		setGlobalVariable("attached", str(attached))

		# only reposition side where card is attached to, if not being played
		if card._id not in being_played:
			if target.controller == me:
				reposition_cards(target.controller)
			else:
				remoteCall(target.controller, "reposition_cards", [target.controller._id])
			

	elif len(target) == 0:
		setGlobalVariable("attached", str(attached))

		# only reposition side of card controller, if card is not being played
		if card._id not in being_played:
			if card.controller == me:
				reposition_cards(card.controller)
			else:
				remoteCall(card.controller, "reposition_cards", [card.controller._id])

	else:
		whisper("target a single card to attach or none to detach")
	# }}}

def update_attached(attached): # {{{
	changed_attached = False

	#cards in table
	group_ids = list(card._id for card in table)

	# remove targets not in group anymore
	for target in attached.keys():
		if target not in group_ids:
			tmp = attached.pop(target)
			changed_attached = True

	# remove attached cards not in group anymore
	for idlist in attached.values():
		for cardid in idlist:
			if cardid not in group_ids:
				idlist.remove(cardid)
				changed_attached = True
	
	# remove target if no ids are attached
	for target in attached.keys():
		if len(attached[target]) == 0:
			attached.pop(target)
			changed_attached = True

	if changed_attached:
		setGlobalVariable("attached",str(attached))
	return attached # }}}

def get_card_width(card): # {{{
	ret = 0
	if card.orientation == Rot90 or card.orientation == Rot270:
		ret = card.height()
	else:
		ret = card.width()
	return ret # }}}

def arrange_cards(group, x=0, y=0): # {{{
	#if not me.isActivePlayer:
		#return
	reposition_cards(me)
	# }}}

def reposition_cards(player): # {{{
	mute()

	if type(player) == type(int()):
		player = Player(player)

	attached = eval(getGlobalVariable("attached"))
	attached = update_attached(attached)

	# get being played card ids
	being_played = eval(getGlobalVariable("response_stack"))
	being_played = get_cards_on_stack(being_played)


	active_players = eval(getGlobalVariable("seating_order"))
	active_players_on_side = list(Player(pid) for pid in active_players
									if Player(pid).hasInvertedTable() == player.hasInvertedTable())

	player_width = {}
	player_cards = {}

	# players on my side
	for p in active_players_on_side:
		cards = categorize_cards(p, table, attached, being_played)
		cards = sort_cards(p, cards, attached)
		cards, width = calc_local_card_pos(p, cards, attached, being_played)
		if width != 0:
			player_width[p._id] = width
			player_cards[p._id] = cards

	sign = -1 if player.hasInvertedTable() else 1
	start_x = -1 * ( (sum(player_width.values()) + (len(player_width)-1) * PLAYER_SPACER)/2 )

	# transform to global coords
	controlled_cards = {}
	index = 0
	for pid in player_width.keys():
		if not player.hasInvertedTable():
			start_x += player_width[pid]

		for card, x, y in player_cards[pid]:
			new_x = start_x + x
			new_y = sign * INITIAL_ROW_OFFSET + y
			controlled_cards.setdefault(card.controller._id, []).append( [card._id, index, new_x, new_y] )
			index = index + 1

		if player.hasInvertedTable():
			start_x += player_width[pid]

		start_x += PLAYER_SPACER

	# move the cards
	for pid in controlled_cards.keys():
		if pid == me._id:
			move_cards(controlled_cards[pid])
		else:
			remoteCall(Player(pid), "move_cards", [ str(controlled_cards[pid]) ])
	# }}}

def move_cards(cardlist): # {{{
	mute()
	if cardlist:
		if type(cardlist) == type(str()):
			cardlist = eval(cardlist)
		if cardlist:
			for cid, index, x, y in cardlist:
				card = Card(cid)
				if not cid in inplay_since_SOT:
					card.highlight = NSOTColor
				card.moveToTable(x, y)
				card.setIndex(index)
	# }}}

def categorize_cards(player, group, attached, being_played): # {{{
	cards = { 'fac': [], 'res': [], 'itm': [], 'loc': [], 'chr': [] , 'oog': [], 'tok': []}

	for card in group:
		# don't add if card is being played
		if card._id in being_played:
			continue

		# don't add if card is attached
		is_attached = False
		for ids in attached.itervalues():
			if card._id in ids:
				is_attached = True
				break
		if is_attached:
			continue

		if card.controller == player:
			type = card.type.lower()

			if has_oog_marker(card):
				cards['oog'].append(card)
			elif card.properties['card number'].lower() == 'token':
				cards['tok'].append(card)
			elif card.isFaceUp == False:
				cards['res'].append(card)
			elif type == 'resource':
				cards['res'].append(card)
			elif type == 'faction':
				cards['fac'].append(card)
			elif type == 'item':
				cards['itm'].append(card)
			elif type == 'location':
				cards['loc'].append(card)
			elif type == 'character':
				cards['chr'].append(card)
	return cards # }}}

def sort_cards(player, categorized_cards, attached): # {{{
	ret = {}
	for type in categorized_cards.iterkeys():
		tmplist = []
		for card in categorized_cards[type]:
			if type == 'oog':
				separate = False
				oog_name = ""
				for marker in card.markers:
					if marker[0].lower()[:3] == 'oog':
						oog_name = marker[0]
						break
				tmplist.append([card, separate, oog_name])

			elif type == 'tok':
				separate = False
				if len(card.markers) or len(attached.get(card._id,[])):
					separate = True
				tmplist.append([card, separate, card.position[0]])

			elif type == 'res':
				separate = False
				facedown = not card.isFaceUp
				if facedown:
					name = 'card'
					trade = 'facedown'
				else:
					name = card.name
					trade = card.trade
				tmplist.append([card, separate, facedown, trade, name, card.position[0] ])

			else:
				separate = True
				tmplist.append([card, separate, card.position[0]])

		# sort the cards and separate where needed
		if type == 'oog':
			tmplist = sorted(tmplist, key=itemgetter(2)) # primary key: marker name
			for i in range(len(tmplist)):
				if i == len(tmplist)-1:
					break
				# separate different oog markers
				if tmplist[i][2] != tmplist[i+1][2]:
					tmplist[i+1][1] = True

		elif type == 'tok':
			tmplist = sorted(tmplist, key=itemgetter(2), reverse=(not player.hasInvertedTable())) # secondary key: current x pos
			tmplist = sorted(tmplist, key=itemgetter(1), reverse=True) # primary key: separated
			irange = range(len(tmplist))
			irange.reverse()
			for i in irange:
				if i == 0:
					break
				# compare separated
				if tmplist[i][1] != tmplist[i-1][1]:
					tmplist[i][1] = True

		elif type == 'chr':
			tmplist = sorted(tmplist, key=itemgetter(2), reverse=(not player.hasInvertedTable())) # primary key: current x pos

		elif type == 'res':
			tmplist = sorted(tmplist, key=itemgetter(5), reverse=(not player.hasInvertedTable())) # x position
			tmplist = sorted(tmplist, key=itemgetter(4)) # name
			tmplist = sorted(tmplist, key=itemgetter(3)) # trade
			tmplist = sorted(tmplist, key=itemgetter(2), reverse=True) # facedown

		else:
			tmplist = sorted(tmplist, key=itemgetter(2), reverse=(not player.hasInvertedTable())) # primary key: current x pos

		if tmplist:
			tmplist = list([j[0],j[1]] for j in tmplist)
		ret[type] = tmplist
	return ret # }}}

def calc_local_card_pos(player, sorted_cards, attached, being_played): # {{{
	all_cards = []

	x = 0
	y = -1 * CARD_HEIGHT if player.hasInvertedTable() else 0

	sign = 1 if player.hasInvertedTable() else -1

	layout = get_layout(player)
	spacer = get_layout_spacer(player)
	res_attach_left = get_layout_res_attach_left(player)

	for row in layout:
		x_min, x_max = 0, 0
		cards_in_row = []
		row.reverse()
		first_in_row = True
		for type in row:
			if len(sorted_cards[type]) == 0:
				continue

			first_of_type = True

			if type == 'res':
				tmp_spacer = spacer['resource']
			else:
				tmp_spacer = spacer['same']

			for card, separate in sorted_cards[type]:

				deplete_width = get_card_width(card) - CARD_WIDTH

				if first_in_row:
					first_in_row = False
					first_of_type = False
					#x += sign * (get_card_width(card) - CARD_WIDTH) if player.hasInvertedTable() else sign * get_card_width(card)
					x += 0 if player.hasInvertedTable() else sign * CARD_WIDTH
				elif first_of_type:
					first_of_type = False
					x += sign * spacer['group']
					x += sign * CARD_WIDTH
				else:
					if separate:
						x += sign * (CARD_WIDTH + spacer['card'])
					else:
						x += sign * tmp_spacer
						deplete_width = 0

				# function to recursivley get card and all attached to it
				def get_attached(result, card, attached, being_played, x, y, dx, dy, depth):
					tmp_x = x
					tmp_y = y
					for attid in attached.get(card._id,[]):
						# dont attach cards that are being played
						if attid in being_played:
							continue

						if depth % 2 == 1:
							tmp_y += 1.5 * dy
						else:
							tmp_x += dx
							tmp_y = y + dy

						tmp = []
						tmp = get_attached(tmp, Card(attid), attached, being_played, tmp_x, tmp_y, dx, dy, depth+1)
						result.extend(tmp)
					result.append([card, x, y])
					return result

				
				if type == 'fac':
					att_dir = sign if res_attach_left else -1 * sign
					dx = att_dir * spacer['resource']
					dy = 0
				else:
					att_dir = -1* sign
					dx = att_dir * spacer['attach_x']
					dy = sign * spacer['attach_y']

				attached_cards = get_attached([], card, attached, being_played, x, y, dx, dy, 0)

				att_x_max = attached_cards[0][1]
				att_x_min = attached_cards[0][1]
				for attcard, tmp_x, tmp_y in attached_cards:
					att_x_max = tmp_x if tmp_x > att_x_max else att_x_max
					att_x_min = tmp_x if tmp_x < att_x_min else att_x_min

				att_width = att_x_max - att_x_min

				if att_width > deplete_width:
					direction = copysign(1, att_width)
					if att_dir != sign:
						for i in range(len(attached_cards)):
							attached_cards[i][1] += sign * att_width
					x += sign * att_width
				else:
					for i in range(len(attached_cards)):
						attached_cards[i][1] += sign * deplete_width
					x += sign * deplete_width

				if type == 'fac':
					a = player.hasInvertedTable()
					b = res_attach_left
					xor = (a or b) and not (a and b)
					attached_cards = sorted(attached_cards, key=itemgetter(1), reverse=xor) # secondary key: x pos
				else:
					attached_cards = sorted(attached_cards, key=itemgetter(1), reverse=(not player.hasInvertedTable())) # secondary key: x pos
				attached_cards = sorted(attached_cards, key=itemgetter(2), reverse=(player.hasInvertedTable())) # primary key: y pos

				cards_in_row.extend(attached_cards)
				# end of card in type loop

			# end of type in row loop

		# for inverted table, last card's width has to be accounted for
		if player.hasInvertedTable() and row[-1] == type and len(cards_in_row):
			x += get_card_width(cards_in_row[-1][0])

		if cards_in_row:

			x_max = x if x > x_max else x_max
			x_min = x if x < x_min else x_min

			row_y_max = cards_in_row[0][2]
			row_y_min = cards_in_row[0][2]
			for attcard, tmp_x, tmp_y in cards_in_row:
				row_y_max = tmp_y if tmp_y > row_y_max else row_y_max
				row_y_min = tmp_y if tmp_y < row_y_min else row_y_min

			row_height = row_y_max - row_y_min

			for i in range(len(cards_in_row)):
				cards_in_row[i][2] += -1 * sign * row_height
			y += -1 * sign * row_height

			all_cards.append([cards_in_row, x_max-x_min])

		y += -1 * sign * (spacer['row'] + CARD_HEIGHT)
		x = 0
		# end of row loop

	max_width = max( width for row, width in all_cards ) if all_cards else 0
	centered = []
	for i in range(len(all_cards)):
		if all_cards[i][1] != max_width:
			for j in range(len(all_cards[i][0])):
				all_cards[i][0][j][1] += sign *( (max_width - all_cards[i][1])/2 )
		centered.extend(all_cards[i][0])
	
	return (centered, max_width) # }}}

# vim:foldmethod=marker
