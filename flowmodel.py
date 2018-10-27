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
    def action(self, action, target):
        if action not in dir(self):
            raise InvalidManipulation("Action %s is not available for type %s"%(action,type(self)))
        a = getattr(self, action)
        a(target)

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
    def add(self, thing, position):
        super(Grid,self).add(thing,position)
        self.state_dict["rows"][position[1]][position[0]] = thing["key"]
    def remove(self, thing):
        super(Grid,self).add(thing)
        self.state_dict["rows"][thing["position"][1]][thing["position"][0]] = None

@add_type("thing")
class Thing(Blob):
    pass

class CardOwnershipPermission(ImpermissiveManipulation):
    pass
@add_type("card")
class Card(Thing):
    @operation
    def play(self, space):
        if(self.location["player"]!=self.world["current_player"]):
            raise CardOwnershipPermission("You dont own that card")
        if(space["player"]==self.world["current_player"]):
            raise InvalidManipulation("You cant play on yourself")
        self.model.move_to_space(self.key, space.key)
    @operation
    def draw(self, space):
        if self.location["type"]!="deck":
            raise InvalidManipulation("You must draw from a deck")
        self.model.move_to_space(self.key, space.key)

@add_type("world")
class World(Blob):
    @operation
    def end_turn(self):
        players = ["player1","player2"]
        players.remove(self.state_dict["current_player"])
        self.state_dict["current_player"] = players[0]
        self.model.build_index()

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
    def walk(self):
        for space in self.state["spaces"]:
            loc = makeob(space, self.world, self.world, self)
            yield loc
            for thing in space["things"]:
                yield makeob(thing, loc, self.world, self)
    def build_index(self):
        self.state["time"] = self.state.get("time",0)+1
        self.index = {}
        self.world = World(self.state, None, None, self)
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
    def move_to_space(self, thing_key, space2_key):
        thing, space2 = self.get_objects(thing_key, space2_key)
        space1 = self.get_object(thing.location["key"])
        space1.remove(thing)
        space2.add(thing)
        self.build_index()

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
    state = {
        "key":"world",
        "time":0,
        "current_player":"player1",
        "players":{
        },
        "spaces":[
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
                    ["red", "blue", "green", "black"],
                    ["red", "blue", "green", "black"]
                ]
            }
        ]
    }
    card_key = [0]
    def add_card():
        card_key[0] += 1
        return {
                    "key": card_key[0],
                    "type": "card",
                    "back": "1",   #Which back to show
                    "color": random.choice(["red","blue","green","black"])
                }
    m = GameModel(state)
    for player in ["deck1","deck2"]:
        for i in range(3):
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
