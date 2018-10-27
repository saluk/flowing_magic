import random

state = {
    "key":"world",
    "time":0,
    "current_player":"player1",
    "players":{
        "2":{
            "user_id":"2",
            "player_key":"player1"
        },
        "3":{
            "user_id":"3",
            "player_key":"player2"
        },
    },
    "spaces":[
        {
            "key":"playarea1",
            "player":"player1",
            "type":"tableau",
            "things":[
            ]
        },
        {
            "key":"playarea2",
            "player":"player2",
            "type":"tableau",
            "things":[
            ]
        }
    ]
}


class ModelError(Exception):
    pass
class InvalidManipulation(ModelError):
    pass
class MissingObject(InvalidManipulation):
    pass
class MissingType(InvalidManipulation):
    pass

class ImpermissiveManipulation(ModelError):
    pass

types = {}

class Blob(object):
    def __init__(self, state_dict, location, world, model):
        self.state_dict = state_dict
        self.location = location
        self.world = world
        self.model = model
        self.key = self.state_dict["key"]
    def __getitem__(self, key):
        return self.state_dict[key]
    def action(self, player, action, target, spot=None):
        if action not in dir(self):
            raise InvalidManipulation("Action %s is not available for type %s"%(action,type(self)))
        if not player["player_key"]==self.world["current_player"]:
            raise ImpermissiveManipulation("It is not this player's turn")
        a = getattr(self, action)
        a(target, spot)

def add_type(t):
    def f(cls):
        cls.typematch = t
        types[t] = cls
        return cls
    return f

def operation(f):
    def newf(*args, **kwargs):
        return f(*args, **kwargs)
    return newf

@add_type("space")
class Space(Blob):
    def add(self, thing, position=None):
        thing.state_dict["position"] = position
        if thing["key"] in [x["key"] for x in self.state_dict["things"]]:
            raise InvalidManipulation(thing["key"],"is already in",self["key"])
        self.state_dict["things"].append(thing.state_dict)
    def remove(self, thing):
        for ob in self.state_dict["things"]:
            if ob["key"]==thing["key"]:
                self.state_dict["things"].remove(ob)
                return
        raise InvalidManipulation(thing["key"],"is not in",self["key"])
@add_type("tableau")
class Tableau(Space):
    def move_to_space(self):
        if self["player"] != self.world["current_player"]:
            raise ImpermissiveManipulation("Wrong Player")

@add_type("hand")
class Hand(Space):
    pass

@add_type("deck")
class Deck(Space):
    pass

@add_type("grid")
class Grid(Space):
    stack_limit = 2
    def __init__(self, *args, **kwargs):
        super(Grid, self).__init__(*args, **kwargs)
        self.build_index()
    def add(self, thing, position):
        stack = self.state_dict["rows"][position[1]][position[0]]
        super(Grid,self).add(thing,position)
        stack.append(thing["key"])
        self.spot_index[thing["key"]] = position
    def remove(self, thing):
        super(Grid,self).remove(thing)
        print(thing["position"])
        position = self.spot_index[thing["key"]]
        del self.spot_index[thing["key"]]
        self.state_dict["rows"][position[1]][position[0]].remove(thing["key"])
    def build_index(self):
        self.spot_index = {}
        for ri,row in enumerate(self.state_dict["rows"]):
            for ci,col in enumerate(row):
                for card_key in col[1:]:
                    self.spot_index[card_key] = [ci,ri]
    def rotate(self):
        rows = self.state_dict["rows"]
        print(rows)
        colors = [x[0] for x in rows[0]]
        new_row = []
        next_card = None
        for col in rows[0]:
            stack = []
            stack.append(colors.pop(0))
            if next_card:
                stack.append(next_card)
            next_card = col[1] if len(col)>1 else None
            new_row.append(stack)
        rows[0] = new_row
        right_hand = next_card

        colors = [x[0] for x in rows[1]]
        new_row = []
        for col in reversed(rows[1]):
            stack = []
            stack.append(colors.pop(-1))
            if next_card:
                stack.append(next_card)
            next_card = col[1] if len(col)>1 else None
            new_row.append(stack)
        left_hand = next_card
        rows[1] = list(reversed(new_row))

        if left_hand:
            rows[0][0].append(left_hand)
        print("new:",self.state_dict["rows"])
        self.build_index()
    def activate(self):
        target = "player2"
        for row in self.state_dict["rows"]:
            for col in row:
                color,cards = col[0],col[1:]
                if cards:
                    self.model.get_object(cards[0]).activate(color,target)
            target = "player1"

def test_grid():
    d = {
            "key":"blah",
            "rows":
        [
            [["red","1"],["blue"],["green"],["black"]],
            [["red"],["blue"],["green"],["black","1"]]
        ]

    }
    g = Grid(d, None, None, None)
    g.rotate()
    g.rotate()
    g.rotate()
    g.rotate()
if __name__=="__main__":
    test_grid()

@add_type("thing")
class Thing(Blob):
    pass

class CardOwnershipPermission(ImpermissiveManipulation):
    pass
@add_type("card")
class Card(Thing):
    def mana_block(self):
        if self.model.current_player_model()["mana"]<self["mana"]:
            raise InvalidManipulation("Not enough mana")
        self.model.current_player_model()["mana"] -= self["mana"]
    @operation
    def play(self, space):
        self.mana_block()
        if(self.location["player"]!=self.world["current_player"]):
            raise CardOwnershipPermission("You dont own that card")
        if(space["player"]==self.world["current_player"]):
            raise InvalidManipulation("You cant play on yourself")
        self.model.move_to_space(self.key, space.key)
    @operation
    def draw(self, space, *args, **kwargs):
        if self.location["type"]!="deck":
            raise InvalidManipulation("You must draw from a deck")
        if self.model.get_player(self.world["current_player"])["mana"]<=0:
            raise InvalidManipulation("You have no mana to draw")
        self.model.get_player(self.world["current_player"])["mana"]-=1
        self.model.move_to_space(self.key, space.key)
    @operation
    def playflow(self, space, spot):
        self.mana_block()
        spot = [int(x) for x in spot.split(",")]
        if not space.state_dict["type"] == "grid":
            raise InvalidManipulation("You must play a flow onto a grid")
        #TODO more distinct card types
        #if not self.state_dict["card_type"]=="flow":
        #    raise InvalidManipulation("You cannot put a non flow card into the flow")
        if self.state_dict["card_type"]=="flow":
            if self.world["current_player"]=="player1" and spot[1]!=1:
                raise ImpermissiveManipulation("Play on your side")
            if self.world["current_player"]=="player2" and spot[1]!=0:
                raise ImpermissiveManipulation("Play on your side")
            stack = space.state_dict["rows"][spot[1]][spot[0]]
            if len(stack)>=space.stack_limit:
                raise InvalidManipulation("Stack limit reached")
            self.model.move_to_space(self.key, space.key, spot)
        elif self.state_dict["card_type"]=="instant":
            target = {"player1":"player2","player2":"player1"}[self.world["current_player"]]
            self.activate(self.state_dict["color"],target)
    def activate(self, color, target):
        if color!=self.state_dict["color"]:
            return
        target = self.model.get_player(target)
        if self["force"]:
            target["force"] -= self["force"]
        self.model.move_to_space(self.key,"purged")
        self.world.have_winner()


@add_type("world")
class World(Blob):
    @operation
    def end_turn(self, *args):
        self.model.get_player(self.state_dict["current_player"])["mana"] += 1
        players = ["player1","player2"]
        players.remove(self.state_dict["current_player"])
        self.state_dict["current_player"] = players[0]
        self.model.get_object("flowarea").rotate()
        self.model.get_object("flowarea").activate()
        self.model.build_index()
    def have_winner(self):
        loser = False
        for player in list(self["players"].values()):
            if player["force"]<0:
                player["result"] = "lost"
                loser = True
        for player in list(self["players"].values()):
            if loser and not "result" in player:
                player["result"] = "won"

@add_type("player")
class Player(Blob):
    pass

def makeob(ob, loc, world, model):
    t = ob.get("type",None)
    for cls in types.values():
        if cls.typematch==t:
            return cls(ob, loc, world, model)
    raise MissingType(key,t,"type could not be found")

class GameModel(object):
    def __init__(self, state):
        if not state: state = {}
        self.state = state
        self.build_index()
    def make_object(self, data):
        return makeob(data, None, self.world, self)
    def get_object(self, key):
        if key in self.index:
            return self.index[key]
        raise MissingObject(key,"could not be found")
    def get_objects(self, *keys):
        return [self.get_object(key) for key in keys]
    def get_player(self, player_key):
        for p in list(self.state["players"].values()):
            if p["player_key"]==player_key:
                return p
        raise InvalidManipulation("No player "+str(player_key))
    def walk(self):
        for space in self.state["spaces"]:
            loc = makeob(space, self.world, self.world, self)
            yield loc
            for thing in space["things"]:
                yield makeob(thing, loc, self.world, self)
    def current_player_model(self):
        for p in list(self.state["players"].values()):
            if p["player_key"] == self.world["current_player"]:
                return p
        raise Exception("THERE'S NO CURRENT PLAYER!")
    def build_index(self):
        self.state["time"] = self.state.get("time",0)+1
        self.index = {}
        self.world = World(self.state, None, None, self)
        self.world.world = self.world
        self.index["world"] = self.world
        for space in self.state["spaces"]:
            loc = makeob(space, self.world, self.world, self)
            self.index[space["key"]] = loc
            for thing in space["things"]:
                self.index[thing["key"]] = makeob(thing, loc, self.world, self)
    def create_thing_in_space(self, thing, space1_key):
        space1 = self.get_object(space1_key)
        space1.add(thing)
        self.build_index()
    def move_to_space(self, thing_key, space2_key, position=None):
        thing, space2 = self.get_objects(thing_key, space2_key)
        space1 = self.get_object(thing.location["key"])
        space1.remove(thing)
        space2.add(thing, position)
        self.build_index()
    def add_player(self, user_id):
        choices = ["player1","player2"]
        for p in list(self.state["players"].values()):
            choices.remove(p["player_key"])
        p = {"user_id": str(user_id), "mana":15, "player_key":random.choice(choices), "force":25}
        self.state["players"][str(user_id)] = p

def expect_exception(exc,f,args):
    try:
        f(*args)
    except exc:
        return True
    raise AssertionError("Expected exception",exc,"not raised")

def default_state():
    return GameModel(state)
    
def from_state(state):
    return GameModel(state)

def newgame():
    row_order = ["red","blue","green","black"]
    random.shuffle(row_order)
    state = {
        "key":"world",
        "time":0,
        "current_player":"player1",
        "players":{
        },
        "spaces":[
            {"key":"purged","type":"hand","player":"none","things":[]},
            {
                "key":"hand1",
                "player":"player1",
                "type":"hand",
                "things":[
                ]
            },
            {
                "key":"deck1",
                "player":"player1",
                "type":"deck",
                "things":[
                ]
            },
            {
                "key":"hand2",
                "player":"player2",
                "type":"hand",
                "things":[
                ]
            },
            {
                "key":"deck2",
                "player":"player2",
                "type":"deck",
                "things":[
                ]
            },
            {
                "key":"flowarea",
                "type":"grid",
                "things":[
                ],
                "rows":[
                    [[x] for x in row_order],
                    [[x] for x in row_order]
                ]
            }
        ]
    }
    card_key = [0]
    def add_card():
        card_key[0] += 1
        d = {
                    "key": str(card_key[0]),
                    "type": "card",
                    "back": "1",   #Which back to show
                    "color": random.choice(["red","blue","green","black"]),
                    "card_type": random.choice(["instant","flow"]),
                    "mana": random.randint(1,4),
                    "force": random.randint(2,6)
                }
        return d
    m = GameModel(state)
    for player in ["deck1","deck2"]:
        for i in range(30):
            m.create_thing_in_space(m.make_object(add_card()), player)
    for player in ["hand1","hand2"]:
        for i in range(3):
            m.create_thing_in_space(m.make_object(add_card()), player)
    return m

if __name__ == "__main__":
    new = newgame()
    new.state["your_id"] = "5"
    new.state["player1_id"] = "5"
    assert new.your_player_key() == "player1", new.your_player_key()
    new.get_object("flowarea").add(new.make_object({"type":"card","key":"6"}),[1,1])
    assert new.state["spaces"][2]["rows"][1][1]=="6"

def test1():
    m = GameModel(state)
    assert m.get_object("playarea1")["type"]=="tableau"
    assert m.get_object("2")["type"]=="card"
    m.move_to_space("1","playarea2")
    assert m.get_object("1").location==m.get_object("playarea2"),(m.get_object("1").location,m.get_object("playarea2"))
    assert expect_exception(MissingObject,m.move_to_space,["5","playarea2"])
    assert expect_exception(MissingObject,m.move_to_space,["4","playarea3"])
    assert expect_exception(InvalidManipulation,m.get_object("2").play,[m.get_object("playarea1")])
    m.get_object("2").play(m.get_object("playarea2"))
    assert expect_exception(CardOwnershipPermission,m.get_object("2").play,[m.get_object("playarea1")])
    m.get_object("world").end_turn()
    m.get_object("2").play(m.get_object("playarea1"))
