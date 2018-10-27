from kivy.app import App
from kivy.uix.relativelayout import RelativeLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.widget import Widget
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.recyclelayout import RecycleLayout
from kivy.uix.listview import ListView
from kivy.uix.stacklayout import StackLayout
from kivy.uix.scrollview import ScrollView
from kivy.properties import StringProperty, ObjectProperty, BooleanProperty
from kivy.clock import Clock
from kivy.animation import Animation
from kivy.graphics import *
from kivy.core.audio.audio_sdl2 import MusicSDL2
from kivy.core.window import Window
from kivy.network.urlrequest import UrlRequest

import math
import random
import json
import requests

import flowmodel as model

import sys

SERVER="http://tinycrease.com:5000"
SERVER="http://127.0.0.1:5000"
CARD_SIZE=[200,250]
DEFAULT_SPEED=0.05

users = [{"email":"bob@bob.com","password":"password"},
{"email":"sara@sara.com","password":"password"}]
user = users[int(sys.argv[1])] if len(sys.argv)>=2 else None

try:
    import Cookie
except:
    import http.cookies as Cookie
    
def get_headers(req):
    d1 = req._resp_headers
    d2 = {}
    for k in d1:
        d2[k.lower()] = d1[k]
    return d2
    
class Network(object):
    cookies=Cookie.SimpleCookie()
    def get_request(self, endpoint, on_success=None, data=None):
        def _cookies(req):
            set_cookies = get_headers(req).get("set-cookie",None)
            if set_cookies:
                self.cookies.load(set_cookies)
            print("cookies:",str(self.cookies))
        def _on_success(req, response):
            _cookies(req)
            on_success(response)
        def _on_redirect(req, response):
            _cookies(req)
            print("REDIRECT",vars(req))
            url = get_headers(req).get('location',None)
            self.get_request("/"+url.split("//",1)[1].split("/",1)[1], on_success=on_success)
        def _on_error(req, response):
            print("ERROR",vars(req),vars(response))
        def _on_failure(req, response):
            print("FAILURE",vars(req),response)
        submit_cookies = str(self.cookies).split(": ",1)[1] if self.cookies else ""
        print("access","%s%s"%(SERVER,endpoint))
        print("Submit cookies:",submit_cookies)
        if data:
            req = UrlRequest("%s%s"%(SERVER,endpoint), 
                on_success=_on_success,
                on_redirect=_on_redirect,
                on_error=_on_error,
                on_failure=_on_failure,
                req_body=json.dumps(data),
                req_headers={"Content-Type":"application/json","Cookie":submit_cookies})
        else:
            print("GET: ","%s%s"%(SERVER,endpoint))
            req = UrlRequest("%s%s"%(SERVER,endpoint), 
                    on_redirect=_on_redirect,
                    on_success=_on_success, 
                    on_error=_on_error,
                    on_failure=_on_failure,
                    req_headers={"Cookie":submit_cookies})
network = Network()

class EntryField(BoxLayout):
    text = StringProperty()
    label = StringProperty()
    password = BooleanProperty(False)

class MenuBoxLayout(BoxLayout):
    pass

class MainMenu(Widget):
    email = StringProperty()
    password = StringProperty()
    def __init__(self, *args, **kwargs):
        super(MainMenu, self).__init__(*args, **kwargs)
        if user:
            self.email = user["email"]
            self.password = user["password"]
        self.current_mode = self.show_login_screen
        self.game_id = None
        self.gv = None
    def on_size(self, widget, size):
        print("window size set to",size)
        ww,wh = size
        global CARD_SIZE
        cw = ww/8
        ch = cw*(4.0/3.0)
        CARD_SIZE = cw,ch
        print(CARD_SIZE)
        self.current_mode()
    def clear_widgets(self):
        super(MainMenu, self).clear_widgets()
        if self.gv:
            self.gv.disconnect()
    def show_login_screen(self):
        self.current_mode = self.show_login_screen
        print("SHOWING LOGIN SCREEN")
        self.clear_widgets()
        print("background size",self.size)
        bl = MenuBoxLayout(id="boxlayout",
            orientation="vertical",
            width=self.width,
            size_hint= [None, None],
            spacing=10
                )
        self.add_widget(bl)
        self.emailbox = EntryField(text=self.email, label="Email:", id="emailbox")
        bl.add_widget(self.emailbox)
        self.passwordbox = EntryField(text=self.password, label="Password:", id="passwordbox", password=True)
        bl.add_widget(self.passwordbox)
        self.login = Button(text="Login",height=50,size_hint_y=None)
        self.login.bind(on_press=self.do_login)
        bl.add_widget(self.login)
        bl.pos = [0, self.height-bl.height*2]
        self.bl = bl
    def show_games(self):
        self.current_mode = self.show_games
        self.clear_widgets()
        self.game_buttons = []
        self.game_list = BoxLayout(orientation="vertical",size_hint_y=None,width=500)
        self.game_list.bind(minimum_height=self.game_list.setter('height'))
        self.scroll_view = ScrollView(size_hint=(1,None), size=(Window.width,Window.height))
        self.scroll_view.add_widget(self.game_list)
        self.add_widget(self.scroll_view)
        def ginfo(game):
            if len(game["users"])<1:
                return "error"
            users = [u for u in game["users"] if u["user_id"]!=self.user_id]
            if users:
                return "id:%s against %s"%(game["id"],users[0]["nickname"])
            return "id:%s (waiting)"%game["id"]
        for game in self.games_current:
            b = Button(text="Resume Game "+ginfo(game),width=500,height=165,size_hint=[None,None])
            b.game_id = game["id"]
            b.bind(on_press=self.activate_game)
            self.game_list.add_widget(b)
            self.game_buttons.append(b)
        for game in self.games_waiting:
            b = Button(text="Join Game "+ginfo(game),width=500,height=165,size_hint=[None,None])
            b.game_id = game["id"]
            b.bind(on_press=self.join_game)
            self.game_list.add_widget(b)
            self.game_buttons.append(b)
        b = Button(text="Create New Game",width=500,height=45,size_hint=[None,None])
        b.bind(on_press=self.new_game)
        self.game_list.add_widget(b)
    def do_login(self, *args):
        def on_success(data):
            self.user_id = data["user_id"]
            self.nickname = data["nickname"]
            print("set user id",self.user_id)
            print("set nickname",self.nickname)
            self.games_current = data["games"]
            self.games_waiting = data["waiting_games"]
            self.show_games()
        network.get_request("/loginclient",on_success,data={"email":self.emailbox.ids.inp.text,
                                                            "password":self.passwordbox.ids.inp.text})
    def new_game(self, button):
        def on_success(data):
            self.activate_game(game_id=data["game_id"])
        network.get_request("/newgame",on_success)
    def join_game(self, button):
        def on_success(data):
            self.activate_game(game_id=button.game_id)
        network.get_request("/join/"+str(button.game_id),on_success)
    def concede(self, button):
        def on_success(data):
            self.show_login_screen()
        network.get_request("/concede/"+str(button.game_id),on_success)
    def opponent_concedes(self):
        self.show_login_screen()
    def back(self, button):
        self.show_login_screen()
    def activate_game(self, button=None, game_id=None):
        self.current_mode = self.activate_game
        if not game_id and button:
            game_id = button.game_id
        if game_id:
            self.game_id = game_id
            self.last_state = None
        self.clear_widgets()
        gv = GameView(self.last_state)
        gv.user_id = self.user_id
        gv.game_id = self.game_id
        gv.last_time = -1
        gv.size = self.size
        gv.root = self
        self.add_widget(gv)
        gv.get_server_state()
        self.gv = gv

class Animations(object):
    def __init__(self):
        self.animations = []
    def animate_card(self, card, *args, **kwargs):
        class cardanim(Animation):
            view=self
            def on_complete(ca, *args):
                self.end_animation()
                self.next_animation()
        self.animations.append((card,cardanim(*args, **kwargs)))
        if len(self.animations)==1:
            self.next_animation()
    def end_animation(self):
        if self.animations:
            del self.animations[0]
    def next_animation(self):
        for a in self.animations:
            a[1].start(a[0])

class GameView(Widget):
    def __init__(self, last_state= None, *args, **kwargs):
        super(GameView,self).__init__(*args, **kwargs)
        self.state = last_state
        self.schedule_update = None

        #self.music = MusicSDL2()
        #self.music.source = "songs/Metre_-_02_-_Digital_Savanna.mp3"
        #self.music.load()
        #self.music.play()
        self.animations = Animations()
        self.space_objects = []
    def get_server_state(self, dt=0, force=False):
        def on_success(data, force=force):
            if data.get("error",None)=="game_closed":
                self.root.opponent_concedes()
                return
            if not data.get("state",None):
                return
            state = data["state"]
            print("setting state",state)
            first = False
            if not self.state:
                first = True
            else:
                if state["time"] <= self.state.state["time"] and not force:
                    return
            self.user_id = data["user_id"]
            self.state = model.from_state(state)
            self.state.auto_increment_time = False
            self.last_time = state["time"]
            self.your_player = state["players"][self.user_id]["player_key"]
            self.their_player = [x for x in ["player1","player2"] if x!=self.your_player][0]
            if first:
                self.build_world()
            self.adapt_model_sync(self.state)
        network.get_request("/game/%s/%s"%(self.game_id,self.last_time), on_success)

    def add_sync_widget(self, widget, match):
        self.add_widget(widget)
        widget.match = match
        self.space_objects.append(widget)

    def find_sync_widget(self, space, flowmodel):
        def is_match(space_object):
            for key in space_object.match:
                value = space_object.match[key]
                if key not in space:
                    return False
                if value!=space[key]:
                    return False
            return True
        for space_object in self.space_objects:
            if is_match(space_object):
                return space_object

    def build_world(self):
        self.play_area = PlayArea(self)
        self.add_sync_widget(self.play_area, {"key":"flowarea"})

        self.their_hand = Hand(self,pos=[CARD_SIZE[0],self.size[1]-CARD_SIZE[1]])
        self.your_hand = Hand(self,pos=[CARD_SIZE[0],0],bgcolor=[1,0.5,0.5,1])
        self.add_sync_widget(self.their_hand,{"type":"hand","player":self.their_player})
        self.add_sync_widget(self.your_hand,{"type":"hand","player":self.your_player})

        self.their_deck = Deck(self,pos=[0,self.size[1]-CARD_SIZE[1]])
        self.your_deck = Deck(self,pos=[0,0])
        self.add_sync_widget(self.their_deck, {"type":"deck","player":self.their_player})
        self.add_sync_widget(self.your_deck, {"type":"deck","player":self.your_player})

        self.card_preview = None

        buttons = [
                ("Concede",self.root.concede),
                ("Back",self.root.back),
                ("End Turn",self.end_turn)
        ]
        y = (len(buttons)-1)*CARD_SIZE[1]/3
        for b in buttons:
            b = Button(text=b[0],on_press=b[1], width=CARD_SIZE[0], height=CARD_SIZE[1]/3,y=y)
            b.game_id = self.game_id
            b.x = self.width-b.width
            self.add_widget(b)
            y-=CARD_SIZE[1]/3

        self.their_mana = Label(text="Mana:",pos=[0,self.size[1]-CARD_SIZE[1]])
        self.your_mana = Label(text="Mana:",pos=[0,CARD_SIZE[1]])
        self.add_widget(self.their_mana)
        self.add_widget(self.your_mana)

        self.server_update = Clock.schedule_interval(self.get_server_state,5)

    def disconnect(self):
        if self.server_update:
            self.server_update.cancel()

    def show_card_preview(self, card):
        if self.card_preview and self.card_preview.shown:
            return
        self.card_preview = card.get_preview()
        self.card_preview.size = [CARD_SIZE[0]*3,CARD_SIZE[1]*3]
        self.card_preview.allow_stretch = True
        self.card_preview.shown = True
        self.card_preview.redraw()
        self.add_widget(self.card_preview)
    def hide_card_preview(self):
        if not self.card_preview or not self.card_preview.shown:
            return
        self.card_preview.source = ""
        self.card_preview.shown = False
        self.remove_widget(self.card_preview)
    def update_card_preview_pos(self, touch):
        if self.card_preview:
            if touch.x<self.width/2:
                self.card_preview.pos[0]=self.width-self.card_preview.width
            else:
                self.card_preview.pos[0]=0
    def on_touch_up(self, touch):
        super(GameView, self).on_touch_up(touch)
        self.hide_card_preview()
    def on_touch_down(self, touch):
        super(GameView, self).on_touch_down(touch)
        self.update_card_preview_pos(touch)
    def on_touch_move(self, touch):
        super(GameView, self).on_touch_move(touch)
        self.update_card_preview_pos(touch)
    def get_card_drop_pos(self,card,touch):
        for space_ob in self.space_objects:
            if space_ob.collide_point(touch.x, touch.y):
                return space_ob.drop_on(card, touch)
    def our_turn(self):
        return self.your_player == self.state.state["current_player"]
    def handle_action(self, action, thing1_key, thing2_key, spot="0"):
        #CLIENT
        print("START HANDLE ACTION",action)
        self.dragging = None
        failed = False
        player = self.state.get_player(self.your_player)
        try:
            self.state.get_object(thing1_key).action(player,action,self.state.get_object(thing2_key),spot)
        except model.ModelError as e:
            import traceback
            traceback.print_exc()
            failed = True
        print("ACTION FAILED?",failed)
        if failed:
            return False
        #self.adapt_model_sync(self.state)
        #SERVER
        print("ACTION SUCCESSFUL")
        def on_success(data):
            if "error" in data:
                self.get_server_state(force=True)
                return
            self.state = model.from_state(data["state"])
            self.adapt_model_sync(self.state)
        network.get_request("/action/%s/%s/%s/%s/%s"%(action,self.game_id,thing1_key,thing2_key,spot),on_success)
        return True
    def end_turn(self, *args):
        return self.handle_action("end_turn","world","world")
    def adapt_model_sync(self, flowmodel):
        state = flowmodel.state
        card_dict = {}

        for p in list(state["players"].values()):
            prefix = {True: "your_", False:"their_"}[p["player_key"] == self.your_player]
            getattr(self,prefix+"mana").text = "Mana: %s"%p["mana"]

        for space in state["spaces"]:
            space_ob = self.find_sync_widget(space, flowmodel)
            if not space_ob:
                continue
            space_ob.is_owned = True
            if "player" in space and space["player"] != self.your_player:
                space_ob.is_owned = False
            space_ob.is_turn = True
            if "player" in space and space["player"] != state["current_player"]:
                space_ob.is_turn = False
            space_ob.model_key = space["key"]
            space_ob.space = space
            space_ob.setup()
            for card in space_ob.cards:
                card_dict[card.model_key] = card
            space_ob.clear()

        for space in state["spaces"]:
            space_ob = self.find_sync_widget(space, flowmodel)
            if not space_ob:
                continue
            can_drag = not space_ob.block_cards()
            for i,thing in enumerate(space["things"]):
                if thing["key"] not in card_dict:
                    card = GameCard(self, x=0, y=400)
                    card_dict[thing["key"]] = card
                    print("card doesn't exist", thing["key"])
                else:
                    card = card_dict[thing["key"]]
                    print("card exists")
                card.model_key = thing["key"]
                card.can_drag = can_drag
                card.show_back = space_ob.show_card_backs()
                card.thing = thing
                card.redraw()
                space_ob.add_card(card)
            for i,thing in enumerate(space["things"]):
                card = card_dict[thing["key"]]
                if card.x==card.dest_x and card.y==card.dest_y:
                    continue
                self.animations.animate_card(card,x=card.dest_x,y=card.dest_y,t='out_quad',duration=card.speed or DEFAULT_SPEED)

class CardSpace(Widget):
    bgcolor = [0.2,0.2,0.2,1]
    is_owned = True
    is_turn = True
    def __init__(self, view, bgcolor=None, *args, **kwargs):
        super(CardSpace, self).__init__(*args, **kwargs)
        self.size_hint = [None, None]
        if bgcolor:
            self.bgcolor = bgcolor
        self.view = view
        self.cards = []
    def block_cards(self):
        return False
    def show_card_backs(self):
        return False
    def setup(self):
        self.canvas.clear()
        with self.canvas.before:
            Color(*self.bgcolor)
            Rectangle(pos=self.pos,size=self.size)
    def readd_cards(self):
        """Only call after we clear widgets"""
        old_cards = self.cards[:]
        self.cards[:] = []
        [self.add_card(card) for card in old_cards]
    def add_card(self, card, index=0):
        self.cards.append(card)
        self.add_widget(card,index=index)
        self.resize_card_spacing()
    def resize_card_spacing(self):
        width = len(self.cards)*CARD_SIZE[0]
        for card in self.cards:
            card.dest_x = (self.size[0]/2)-width/2+(self.cards.index(card)*CARD_SIZE[0])+CARD_SIZE[0]
            card.dest_y = self.y
            card.speed = None
    def remove_card(self, card):
        self.cards.remove(card)
        self.remove_widget(card)
    def find_card_ob(self, card_key):
        match = [c for c in self.cards if c.model_key==card_key]
        if match:
            return match[0]
        return None
    def clear(self):
        while self.cards:
            self.remove_card(self.cards[0])
    def reset_index(self, card, index=0):
        self.remove_card(card)
        print("setting z-index",index)
        self.add_card(card,index=index)
        print("index set",self.get_index(card))
    def on_touch_down(self, touch):
        print("on touch play area")
        super(CardSpace, self).on_touch_down(touch)
    def get_index(self,card):
        return self.cards.index(card)
    def drop_on(self,card,touch):
        return False

class PlayArea(CardSpace):
    bgcolor = [0.2,0.2,0.2,0]
    def __init__(self, *args, **kwargs):
        super(PlayArea, self).__init__(*args, **kwargs)
        self.dest_slots = []
        self.space = None
    def setup(self):
        if not self.space:
            return
        self.dest_slots = []
        self.clear_widgets()
        self.size = [CARD_SIZE[0]*4,CARD_SIZE[1]*2]
        self.pos=[self.view.size[0]/2-self.size[0]/2,self.view.size[1]/2-self.size[1]/2]
        y=CARD_SIZE[1]
        for ri,row in enumerate(self.space["rows"]):
            x=0
            for ci,col in enumerate(row):
                color,cards = col[0],col[1:]
                if color not in ["red","blue","green","black"]:
                    continue
                slot = Image(source="art/cardslots/CardSlotClear-%s.png"%(color.capitalize(),),
                        x=self.x+x,y=self.y+y,
                        size=[CARD_SIZE[0]+10,CARD_SIZE[1]+10])
                slot.col,slot.row = ci,ri
                slot.cards = cards
                self.add_widget(slot)
                self.dest_slots.append(slot)
                x+=CARD_SIZE[0]
            y-=CARD_SIZE[1]
        self.readd_cards()
    def find_slot(self, card):
        for slot in self.dest_slots:
            if card.model_key in slot.cards:
                return slot
    def resize_card_spacing(self):
        for card in self.cards:
            slot = self.find_slot(card)
            card.dest_x = slot.x+10
            card.dest_y = slot.y+10
            card.speed = 0.1
    def drop_on(self, card, touch):
        for slot in self.dest_slots:
            if not slot.collide_point(touch.x, touch.y):
                continue
            return self.view.handle_action("playflow",card.model_key,self.model_key,"%s,%s"%(slot.col,slot.row))

class Hand(CardSpace):
    bgcolor = [0.2,0.2,0.2,1]
    def __init__(self, *args, **kwargs):
        super(Hand, self).__init__(*args, **kwargs)
        self.size = [CARD_SIZE[0]*6,CARD_SIZE[1]+10]
    def setup(self):
        if self.is_turn:
            self.bgcolor = [1,1,1,1]
        super(Hand, self).setup()
    def block_cards(self):
        return not self.is_owned
    def show_card_backs(self):
        return not self.is_owned
    def drop_on(self, card, touch):
        return self.view.handle_action("draw",card.model_key,self.model_key)

class Deck(CardSpace):
    def __init__(self, *args, **kwargs):
        super(Deck, self).__init__(*args, **kwargs)
        self.size = [CARD_SIZE[0]*1.2,CARD_SIZE[1]*1.2]
    def show_card_backs(self):
        return True
    def block_cards(self):
        return True
    def resize_card_spacing(self):
        width = len(self.cards)*CARD_SIZE[0]
        for card in self.cards:
            card.dest_x = self.x+random.randint(-10,10)
            card.dest_y = self.y+random.randint(-10,10)
            card.speed = 0
    def on_touch_down(self, touch):
        if super(Deck, self).on_touch_down(touch):
            return True
        if not self.collide_point(touch.x, touch.y):
            return False
        if not self.cards:
            return False
        self.view.show_card_preview(self.cards[-1].source)
        if not self.is_owned:
            return False
        if self.view.dragging:
            return False
        if not self.view.our_turn():
            return False
        self.cards[-1].begin_drag(touch)
        return True
        #self.down_pos = [touch.x,touch.y]
        #self.reset_position = [self.x,self.y,self.parent.get_index(self)]
        #print("reset_position",self.reset_position)
        #self.view.dragging = self
        #print("setting",self.down_pos)
        #self.parent.reset_index(self)
        #return True


class GameCardPreview(Image):
    thing = None
    show_back = False
    def redraw(self):
        if not self.thing:
            return
        self.clear_widgets()
        if self.show_back:
            self.source = "art/cards/CardBack.png"
            return
        frames = {"red":"art/cards/CardBlank-Red.png",
                "black":"art/cards/CardBlank-Black.png",
                "blue":"art/cards/CardBlank-Blue.png",
                "green":"art/cards/CardBlank-Green.png",
                "yellow":"",
                "white":""
                }
        self.source = frames[self.thing["color"]]
        card_type = self.thing.get("card_type", None)
        type_image = {"combo":"art/cardtypes/Basic/CardTypeBasic-Combo.png",
                "instant":"art/cardtypes/Basic/CardTypeBasic-Instant.png",
                "flow":"art/cardtypes/Basic/CardTypeBasic-Flow.png"
                }.get(card_type,"")
        i = Image(source=type_image,pos=self.pos,size=self.size)
        def set_pos(ob,pos):
            i.pos = pos
        self.bind(pos=set_pos)
        self.add_widget(i)
        if self.thing.get("mana",0)>=0:
            scale = int(0.15*self.width)
            l = Label(text="[b][size=%spx][color=ffffff]%s[/color][/size][/b]"%(scale,self.thing["mana"]),markup=True)
            def set_pos(ob,pos):
                l.pos = [ob.pos[0]+0.25*ob.size[0], ob.pos[1]+0.75*ob.size[1]]
                l.size = [1,1]
            set_pos(self,self.pos)
            self.bind(pos=set_pos)
            self.add_widget(l)


class GameCard(GameCardPreview):
    can_drag = False
    def __init__(self, view, *args, **kwargs):
        super(GameCard,self).__init__(*args, **kwargs)
        self.view = view
        self.size = CARD_SIZE
        self.down_pos = None
        self.view.dragging = None
    def get_preview(self):
        p = GameCardPreview(source=self.source)
        p.thing = self.thing
        return p
    def on_touch_up(self, touch):
        if super(GameCard, self).on_touch_down(touch):
            return True
        if not self.down_pos or not self.view.dragging==self:
            return False
        self.down_pos = None
        self.view.dragging = None
        print(self.pos,self.size,touch.x,touch.y)
        print(self.collide_point(touch.x, touch.y))
        if self.view.get_card_drop_pos(self,touch):
            return True
        self.view.animations.animate_card(self,x=self.reset_position[0],y=self.reset_position[1],t='out_quad',duration=0.5)
        #self.parent.reset_index(self,self.reset_position[2])
        return True
    def on_touch_move(self, touch):
        if super(GameCard, self).on_touch_move(touch):
            return True
        if not self.down_pos or not self.view.dragging==self:
            return False
        diff = [touch.x-self.down_pos[0], touch.y-self.down_pos[1]]
        self.x += diff[0]
        self.y += diff[1]
        self.down_pos = [touch.x, touch.y]
        return True
    def on_touch_down(self, touch):
        print("touch down card")
        if super(GameCard, self).on_touch_down(touch):
            return True
        if not self.collide_point(touch.x, touch.y):
            return False
        self.view.show_card_preview(self)
        if not self.can_drag:
            return False
        if self.view.dragging:
            return False
        if not self.view.our_turn():
            return False
        self.begin_drag(touch)
        return True
    def begin_drag(self,touch):
        self.down_pos = [touch.x,touch.y]
        self.reset_position = [self.x,self.y,self.parent.get_index(self)]
        print("reset_position",self.reset_position)
        self.view.dragging = self
        print("setting",self.down_pos)
        #self.parent.reset_index(self)

class FlowingMagicApp(App):
    def build(self):
        return MainMenu()

if __name__ == "__main__":
    from kivy.config import Config
    FlowingMagicApp().run()
