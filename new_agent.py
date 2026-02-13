from game.players import BasePokerPlayer
import random
import numpy as np
import os
from game.card import Card
import preflop_winrate
import winrate_estimate
import my_evaluator as HandEvaluator


suits = [2,4,8,16]
ranks = list(range(2, 15)) 
full_deck = [Card(suit, rank) for suit in suits for rank in ranks]
SUIT_MAP = {"C":2, "D":4, "H":8, "S":16}
RANK_MAP = {
    "2":2,
    "3":3,
    "4":4,
    "5":5,
    "6":6,
    "7":7,
    "8":8,
    "9":9,
    "T":10,
    "J":11,
    "Q":12,
    "K":13,
    "A":14,
}
VALUE_MAP = {1:"HIGHCARD", 2:"ONEPAIR", 4:"TWOPAIR", 8:"THREECARD", 16:"STRAIGHT", 32:"FLUSH", 
            64:"FULLHORSE", 128:"FOURCARD", 256:"STRAIGHT FLUSH"}

class CFRTreeBuilder:
    def __init__(self):
        self.next_id=0

    def get_next_id(self):
        nid=self.next_id
        self.next_id+=1
        return nid

treebuilder=CFRTreeBuilder()
loaded=None
if os.path.isfile("cfr_values.npz"):
    loaded=np.load("cfr_values.npz", allow_pickle=True)
data={}

class MyPlayer(BasePokerPlayer):
    def __init__(self):
        print("cfr_tree building...")
        self.river_decisiontree=cfr_tree(3,0,True,False,True,False,None, 4)
        self.turn_decisiontree=cfr_tree(2,0,True,False,True,False,self.river_decisiontree, 3)
        self.flop_decisiontree=cfr_tree(1,0,True,False,True,False,self.turn_decisiontree, 2)
        self.pre_decisiontree=cfr_tree(0,0,True,True,True,False,self.flop_decisiontree, 1)
        if os.path.isfile("cfr_values.npz"):
            self.pre_decisiontree.load()
        else:
            print("game_example generating...")
            num_example=25000
            game_example=[generate_gamexample() for i in range(num_example)]
            pot_info={"pot":15, "paid":[5,10], 'paid_cur':[5,10],'raise_prev':[0,0],'raise_cur':[0,0],}
            print("Performing MCCFR")
            for epoch in range(20):
                print(f"epoch= {epoch}")
                for i in range(num_example):
                    self.pre_decisiontree.fit(0,game_example[i],pot_info)
                    self.pre_decisiontree.fit(1,game_example[i],pot_info)
            self.pre_decisiontree.save()
            np.savez_compressed("cfr_values.npz", **{str(k): v for k, v in data.items()})
        
    def declare_action(self, valid_actions, hole_card, round_state):
        print("valid_actions:")
        print(valid_actions)
        if self.pos==-1:
            self.pos=0
        hand=[Card.from_str(hole_card[0]),Card.from_str(hole_card[1])]
        if self.curnode==None: #Handle error
            return valid_actions[1]['action'], valid_actions[1]['amount']
        com=[]
        for c in round_state["community_card"]:
            com.append(Card.from_str(c))
        cardtype=state_num=0
        if self.info["street"]=='preflop':
            rank=[RANK_MAP[hole_card[0][1]],RANK_MAP[hole_card[1][1]]]
            winrate=0
            if hole_card[0][0]==hole_card[1][0]: #同花
                cardtype=preflop_winrate.classification(max(rank[0],rank[1]),min(rank[0],rank[1]))
                winrate=preflop_winrate.lookup(max(rank[0],rank[1]),min(rank[0],rank[1]))
            else:
                cardtype=preflop_winrate.classification(min(rank[0],rank[1]),max(rank[0],rank[1]))
                winrate=preflop_winrate.lookup(min(rank[0],rank[1]),max(rank[0],rank[1]))
            self.prestate=min(3,int(4*winrate))
        else:
            winrate=self.predict_winrate(hole_card, hand, com)
            cardtype=min(4,int(5*winrate))
            street_map={'flop':1, 'turn':2, 'river':3}
            state_num=getstatenum(self.pot_info,street_map[self.info['street']]) + self.prestate*3
            self.prestate=min(3,int(4*winrate))
        
        action=self.curnode.chooseaction(cardtype, state_num)
        print("action:" + action)
        return self.__choice_action(action, valid_actions, round_state)
        """
        choice = self.__choice_action(action, valid_actions, round_state)
        action = choice["action"]
        amount = choice["amount"]
        if action == "raise":
            amount = random.randrange(amount["min"], max(amount["min"], amount["max"]) + 1)
        self.info['paid_curstreet']=amount
        return action, amount
        """
    def __choice_action(self, action, valid_actions, round_state):
        if action=='fold':
            return valid_actions[0]["action"], valid_actions[0]["amount"]
        elif action=='call':
            paid_amount=valid_actions[1]['amount']-self.pot_info['paid_cur'][self.pos]
            self.pot_info['paid_cur'][self.pos]=valid_actions[1]['amount']
            self.pot_info['pot']+=paid_amount
            self.pot_info['paid'][self.pos]+=paid_amount
            self.info['stack'][0]-=paid_amount
            self.curnode=self.curnode.tonextstate('call')
            if self.curnode!=None:
                self.curnode.print_id()
            return valid_actions[1]["action"], valid_actions[1]["amount"]
        else:
            raise_amount=0
            if action=='raise1/2':
                raise_amount=int(self.pot_info['pot']/2)
            elif action=='raise1':
                raise_amount=self.pot_info['pot']
            else: #allin
                raise_amount=min(self.info['stack'][1],self.info['stack'][0]-(self.pot_info['paid_cur'][1-self.pos]-self.pot_info['paid_cur'][self.pos]))
            if raise_amount+valid_actions[1]["amount"]<valid_actions[2]["amount"]['min']:
                raise_amount=valid_actions[2]["amount"]['min']-valid_actions[1]["amount"]
            elif raise_amount+valid_actions[1]["amount"]>max(valid_actions[2]["amount"]['min'],valid_actions[2]["amount"]['max']):
                raise_amount=max(valid_actions[2]["amount"]['min'],valid_actions[2]["amount"]['max'])-valid_actions[1]["amount"] 
            paid_amount=self.pot_info['paid_cur'][1-self.pos]-self.pot_info['paid_cur'][self.pos]+raise_amount
            self.pot_info['pot']+=paid_amount
            self.pot_info['paid'][self.pos]+=paid_amount
            self.pot_info['paid_cur'][self.pos]+=paid_amount
            self.pot_info['raise_cur'][self.pos]+=raise_amount
            self.info['stack'][0]-=paid_amount
            self.curnode=self.curnode.tonextstate(action)
            if self.curnode!=None:
                self.curnode.print_id()
            return valid_actions[2]["action"], raise_amount+valid_actions[1]["amount"]
        
    def predict_winrate(self, hole_card, hand, com):
        if self.info['street']=='preflop':     
            rank=[RANK_MAP[hole_card[0][1]],RANK_MAP[hole_card[1][1]]]
            if hole_card[0][0]==hole_card[1][0]:
                return preflop_winrate.lookup(max(rank[0],rank[1]),min(rank[0],rank[1]))
            else:
                return preflop_winrate.lookup(min(rank[0],rank[1]),max(rank[0],rank[1]))
        else:
            return winrate_estimate.estimate(hand, com)
        
    def receive_game_start_message(self, game_info):
        self.info={}
        print("game_info:")
        print(game_info)
        self.info["stack"]=[game_info["rule"]['initial_stack'], game_info["rule"]['initial_stack']]
        self.info["name"]=game_info['seats'][0]['name']
        self.info['uuid']=game_info['seats'][0]['uuid']
        return

    def receive_round_start_message(self, round_count, hole_card, seats):
        print("\033[31m""round start""\033[0m")
        print("seats:")
        print(seats)
        self.pos=-1 #undecided
        self.info["stack"]=[seats[0]['stack'],seats[1]['stack']]
        self.info['street']='preflop'
        self.pot_info={"pot":15, "paid":[5,10], 'paid_cur':[5,10],'raise_prev':[0,0],'raise_cur':[0,0],}
        self.curnode=self.pre_decisiontree
        return

    def receive_street_start_message(self, street, round_state):
        print("\033[31m""street start""\033[0m")
        self.info["street"]=street
        self.pot_info=resetpotinfo(self.pot_info)
        if street=='preflop':
            self.curnode=self.pre_decisiontree
        elif street=='flop':
            self.curnode=self.flop_decisiontree
        elif street=='turn':
            self.curnode=self.turn_decisiontree
        elif street=='river':
            self.curnode=self.river_decisiontree
        return

    def receive_game_update_message(self, new_action, round_state):
        print("\033[31m"+"game update"+"\033[0m")
        if self.pos==-1:
            self.pos=1
        
        if new_action['player_uuid']!=self.info['uuid']:
            if new_action['action']=='call':
                pay_amount=new_action['amount']-self.pot_info['paid_cur'][1-self.pos]
                self.pot_info['pot']+=pay_amount
                self.pot_info['paid_cur'][1-self.pos]=new_action['amount']
                self.info['stack'][1]-=pay_amount
                self.curnode=self.curnode.tonextstate('call')
            elif new_action['action']=='raise':
                raise_amount=new_action['amount']-self.pot_info['raise_cur'][self.pos]-10*(self.info['street']=='preflop')
                self.pot_info['raise_cur'][1-self.pos]=raise_amount
                pay_amount=new_action['amount']-self.pot_info['paid_cur'][1-self.pos]
                if raise_amount< 0.75*self.pot_info['pot']:
                    self.curnode=self.curnode.tonextstate('raise1/2')
                elif pay_amount<self.info['stack'][1] and self.info['stack'][0]>raise_amount:
                    self.curnode=self.curnode.tonextstate('raise1')
                else:
                    self.curnode=self.curnode.tonextstate('allin')

                self.pot_info['pot']+=pay_amount
                self.pot_info['paid_cur'][1-self.pos]=new_action['amount']
                self.info['stack'][1]-=pay_amount
            if self.curnode!=None:
                self.curnode.print_id()
                
                
    def receive_round_result_message(self, winners, hand_info, round_state):
        pass
    
    def consult_ai(self):
        pos=input("Please enter your position(0=SB, 1=BB):")
        while not pos.isdigit() or (int(pos)!=0 and int(pos)!=1):
            pos=input("Wrong format. Please enter again:")
        hole_card=[None, None]
        hole_card[0]=input("Please enter hand card 1:")
        while len(hole_card[0])!=2 or hole_card[0][0] not in SUIT_MAP or hole_card[0][1] not in RANK_MAP:
            hole_card[0]=input("Wrong format. Please enter again:")
        hole_card[1]=input("Please enter hand card 2:")
        while len(hole_card[1])!=2 or hole_card[1][0] not in SUIT_MAP or hole_card[1][1] not in RANK_MAP:
            hole_card[1]=input("Wrong format. Please enter again:")
        hand=[Card.from_str(hole_card[0]),Card.from_str(hole_card[1])]
        self.pos=int(pos)
        self.curnode=self.pre_decisiontree
        oppraise=True
        allin=False
        self.pot_info={"pot":15, "paid":[5,10], 'paid_cur':[5,10],'raise_prev':[0,0],'raise_cur':[0,0],}
        pos_actioning=0
        while True: #preflop
            action=None
            amount=0
            if pos_actioning!=self.pos:
                action=input("Please enter your opponent's behavior(f=fold, c=call, r=raise or allin):")
                while action!="f" and action!="c" and action!="r" and action!="allin":
                    action=input("Wrong format. Please enter again:")
                if action=="r":
                    amount=input("Please enter the amount your opponent paid in total this round:")
                    while not amount.isdigit() or int(amount)<self.pot_info["paid"][self.pos]:
                        amount=input("Wrong format. Please enter again:")
                if action=="f":
                    print(f"Congratulations! You won {self.pot_info["paid"][1-self.pos]}!")
                    return
                elif action=="c":
                    pay_amount=self.pot_info["paid"][self.pos]-self.pot_info["paid"][1-self.pos]
                    self.pot_info["pot"]+=pay_amount
                    self.pot_info["paid"][1-self.pos]=self.pot_info["paid"][self.pos]
                    self.pot_info["paid_cur"][1-self.pos]+=pay_amount
                    self.curnode=self.curnode.tonextstate('call')
                    if allin==True:
                        self.consult_result(hand, board=[])
                        return
                    if not (pos_actioning==0 and self.pot_info["paid_cur"][1-self.pos]==10):
                        break #go to flop
                elif action=="r":
                    raise_amount=int(amount)-self.pot_info["paid"][self.pos]
                    pay_amount=int(amount)-self.pot_info["paid"][1-self.pos]
                    if raise_amount<0.75*self.pot_info["pot"]:
                        action='raise1/2'
                    else:
                        action='raise1'
                    self.pot_info["pot"]+=pay_amount
                    self.pot_info["paid"][1-self.pos]+=pay_amount
                    self.pot_info["paid_cur"][1-self.pos]+=pay_amount
                    self.pot_info['raise_cur'][1-self.pos]+=raise_amount
                    if oppraise==False:
                        print("Only recommendation:call")
                        pay_amount=int(amount)-self.pot_info["paid"][self.pos]
                        self.pot_info["pot"]+=pay_amount
                        self.pot_info["paid"][self.pos]+=pay_amount
                        self.pot_info["paid_cur"][self.pos]+=pay_amount
                        break
                    oppraise=False
                    self.curnode=self.curnode.tonextstate(action)
                else:
                    if oppraise==False:
                        print("Only recommendation:call")
                        self.pot_info["paid"][1-self.pos]=self.pot_info["paid"][self.pos]=1000
                        self.consult_result(hand, board=[])
                        return
                    allin=True
                    self.pot_info["paid"][1-self.pos]=1000
                    self.curnode=self.curnode.tonextstate("allin")
            else:
                cardtype=0
                rank=[RANK_MAP[hole_card[0][1]],RANK_MAP[hole_card[1][1]]]
                winrate=0
                if hole_card[0][0]==hole_card[1][0]: #同花
                    cardtype=preflop_winrate.classification(max(rank[0],rank[1]),min(rank[0],rank[1]))
                    winrate=preflop_winrate.lookup(max(rank[0],rank[1]),min(rank[0],rank[1]))
                else:
                    cardtype=preflop_winrate.classification(min(rank[0],rank[1]),max(rank[0],rank[1]))
                    winrate=preflop_winrate.lookup(min(rank[0],rank[1]),max(rank[0],rank[1]))
                self.prestate=min(3,int(4*winrate))
                action=self.curnode.chooseaction(cardtype, 0)
                if action=='raise1/2' or action=='raise1':
                    total_amount=self.pot_info["paid"][1-self.pos]+(int(self.pot_info["pot"]/2) if action=='raise1/2' else self.pot_info["pot"])
                print("recommended action:" + action, end='')
                if action=='raise1/2' or action=='raise1':
                    print(" ("+str(total_amount)+")")
                else:
                    print("")

                action=input("Please enter your real behavior(f=fold, c=call, r=raise or allin):")
                while action!="f" and action!="c" and action!="r" and action!="allin":
                    action=input("Wrong format. Please enter again:")
                if action=="r":
                    amount=input("Please enter the amount you paid in total this round:")
                    while not amount.isdigit() or int(amount)<self.pot_info["paid"][1-self.pos]:
                        amount=input("Wrong format. Please enter again:")
                if action=="f":
                    print(f"Unfortunately you lost {self.pot_info["paid"][self.pos]} :(")
                    return
                elif action=="c":
                    pay_amount=self.pot_info["paid"][1-self.pos]-self.pot_info["paid"][self.pos]
                    self.pot_info["pot"]+=pay_amount
                    self.pot_info["paid"][self.pos]=self.pot_info["paid"][1-self.pos]
                    self.pot_info["paid_cur"][self.pos]+=pay_amount
                    self.curnode=self.curnode.tonextstate('call')
                    if allin==True:
                        self.pot_info["paid"][1-self.pos]=self.pot_info["paid"][self.pos]=1000
                        self.consult_result(hand, board=[])
                        return
                    if not (pos_actioning==0 and self.pot_info["paid_cur"][self.pos]==10):
                        break #go to flop
                elif action=="r":
                    raise_amount=int(amount)-self.pot_info["paid"][1-self.pos]
                    pay_amount=int(amount)-self.pot_info["paid"][self.pos]
                    if raise_amount<0.75*self.pot_info["pot"]:
                        action='raise1/2'
                    else:
                        action='raise1'
                    self.pot_info["pot"]+=pay_amount
                    self.pot_info["paid"][self.pos]+=pay_amount
                    self.pot_info["paid_cur"][self.pos]+=pay_amount
                    self.pot_info['raise_cur'][self.pos]+=raise_amount
                    self.curnode=self.curnode.tonextstate(action)
                else:
                    self.pot_info["paid"][self.pos]=1000
                    allin=True
            pos_actioning=1-pos_actioning
        
        print("\n-flop stage\n")
        self.pot_info=resetpotinfo(self.pot_info)
        self.curnode=self.flop_decisiontree
        com=[]
        for i in range(3):
            com.append(input("Enter community card"+str(i+1)+":"))
            while len(com[i])!=2 or com[i][0] not in SUIT_MAP or com[i][1] not in RANK_MAP:
                com[i]=input("Format error. Please enter again:")
            com[i]=Card.from_str(com[i])
        oppraise=True
        allin=False
        pos_actioning=0
        for i in range(3): #flop, turn and river
            while True:
                action=None
                amount=0
                if pos_actioning!=self.pos:
                    action=input("Please enter your opponent's behavior(f=fold, c=call, r=raise or allin):")
                    while action!="f" and action!="c" and action!="r" and action!="allin":
                        action=input("Wrong format. Please enter again:")
                    if action=="r":
                        amount=input("Please enter the amount your opponent paid in total this round:")
                        if not amount.isdigit() or int(amount)<self.pot_info["paid"][self.pos]:
                            amount=input("Wrong format. Please enter again:")
                    if action=="f":
                        print(f"Congratulations! You won {self.pot_info["paid"][1-self.pos]}!")
                        return
                    elif action=="c":
                        pay_amount=self.pot_info["paid"][self.pos]-self.pot_info["paid"][1-self.pos]
                        self.pot_info["pot"]+=pay_amount
                        self.pot_info["paid"][1-self.pos]=self.pot_info["paid"][self.pos]
                        self.pot_info["paid_cur"][1-self.pos]+=pay_amount
                        self.curnode=self.curnode.tonextstate('call')
                        if allin==True:
                            self.consult_result(hand, com)
                            return
                        if not (pos_actioning==0 and self.pot_info["paid_cur"][1-self.pos]==0):
                            break #go to next stage
                    elif action=="r":
                        raise_amount=int(amount)-self.pot_info["paid"][self.pos]
                        pay_amount=int(amount)-self.pot_info["paid"][1-self.pos]
                        if raise_amount<0.75*self.pot_info["pot"]:
                            action='raise1/2'
                        else:
                            action='raise1'
                        self.pot_info["pot"]+=pay_amount
                        self.pot_info["paid"][1-self.pos]+=pay_amount
                        self.pot_info["paid_cur"][1-self.pos]+=pay_amount
                        self.pot_info['raise_cur'][1-self.pos]+=raise_amount
                        if oppraise==False:
                            print("Only recommendation:call")
                            pay_amount=int(amount)-self.pot_info["paid"][self.pos]
                            self.pot_info["pot"]+=pay_amount
                            self.pot_info["paid"][1-self.pos]+=pay_amount
                            self.pot_info["paid_cur"][1-self.pos]+=pay_amount
                            break
                        oppraise=False
                        self.curnode=self.curnode.tonextstate(action)
                    else:
                        if oppraise==False:
                            print("Only recommendation:call")
                            self.pot_info["paid"][1-self.pos]=self.pot_info["paid"][self.pos]=1000
                            self.consult_result(hand, com)
                            return
                        self.pot_info["paid"][1-self.pos]=1000
                        allin=True
                        oppraise=False
                        self.curnode=self.curnode.tonextstate("allin")
                else:
                    winrate=winrate_estimate.estimate(hand, com)
                    state_num=self.prestate*3 + getstatenum(self.pot_info, 0)
                    self.prestate=min(3,int(4*winrate))
                    cardtype=min(4,int(5*winrate))
                    action=self.curnode.chooseaction(cardtype, state_num)
                    if action=='raise1/2' or action=='raise1':
                        total_amount=self.pot_info["paid"][1-self.pos]+(int(self.pot_info["pot"]/2) if action=='raise1/2' else self.pot_info["pot"])
                    print("recommended action:" + action, end='')
                    if action=='raise1/2' or action=='raise1':
                        print(" ("+str(total_amount)+")")
                    else:
                        print("")

                    action=input("Please enter your real behavior(f=fold, c=call, r=raise or allin):")
                    while action!="f" and action!="c" and action!="r" and action!="allin":
                        action=input("Wrong format. Please enter again:")
                    if action=="r":
                        amount=input("Please enter the amount you paid in total this round:")
                        while not amount.isdigit() or int(amount)<self.pot_info["paid"][1-self.pos]:
                            amount=input("Wrong format. Please enter again:")
                    if action=="f":
                        print(f"Unfortunately you lost {self.pot_info["paid"][self.pos]} :(")
                        return
                    elif action=="c":
                        pay_amount=self.pot_info["paid"][1-self.pos]-self.pot_info["paid"][self.pos]
                        self.pot_info["pot"]+=pay_amount
                        self.pot_info["paid"][self.pos]=self.pot_info["paid"][1-self.pos]
                        self.pot_info["paid_cur"][self.pos]+=pay_amount
                        self.curnode=self.curnode.tonextstate('call')
                        if allin==True:
                            self.consult_result(hand, com)
                            return
                        if not (pos_actioning==0 and self.pot_info["paid_cur"][self.pos]==0):
                            break #go to flop
                    elif action=="r":
                        raise_amount=int(amount)-self.pot_info["paid"][1-self.pos]
                        pay_amount=int(amount)-self.pot_info["paid"][self.pos]
                        if raise_amount<0.75*self.pot_info["pot"]:
                            action='raise1/2'
                        else:
                            action='raise1'
                        self.pot_info["pot"]+=pay_amount
                        self.pot_info["paid"][self.pos]+=pay_amount
                        self.pot_info["paid_cur"][self.pos]+=pay_amount
                        self.pot_info['raise_cur'][self.pos]+=raise_amount
                        self.curnode=self.curnode.tonextstate(action)
                    else:
                        self.pot_info["paid"][self.pos]=1000
                        allin=True
                pos_actioning=1-pos_actioning
            if i==0:
                self.curnode=self.turn_decisiontree
                print("\n-turn stage")
            elif i==1:
                self.curnode=self.river_decisiontree
                print("\n-river stage")
            print("")
            if i!=2: # not river
                com.append(input("Enter community card"+str(i+4)+":"))
                while len(com[3+i])!=2 or com[3+i][0] not in SUIT_MAP or com[3+i][1] not in RANK_MAP:
                    com[3+i]=input("Wrong format. Please enter again:")
                com[3+i]=Card.from_str(com[i+3])
            self.pot_info=resetpotinfo(self.pot_info)
            pos_actioning=0
            oppraise=True

        self.consult_result(hand, com)
        return

    def consult_result(self, hand, board):
        if len(board)<5:
            for i in range(len(board)+1, 6, 1):
                board.append(input("Enter community card"+str(i)+":"))
                while len(board[i-1])!=2 or board[i-1][0] not in SUIT_MAP or board[i-1][1] not in RANK_MAP:
                    board[i-1]=input("Wrong format. Please enter again:")
                board[i-1]=Card.from_str(board[i-1])
        opp_hand=[0]*2
        for i in range(2):
            opp_hand[i]=input("Enter opponent's card"+str(i+1)+":")
            while len(opp_hand[i])!=2 or opp_hand[i][0] not in SUIT_MAP or opp_hand[i][1] not in RANK_MAP:
                opp_hand[i]=input("Wrong format. Please enter again:")
            opp_hand[i]=Card.from_str(opp_hand[i])
        my_value=HandEvaluator.eval_hand(hole=hand, community=board)
        opp_value=HandEvaluator.eval_hand(hole=opp_hand, community=board)
        print("Your card type: "+VALUE_MAP[my_value>>20])
        print("Your opponent's card type: "+VALUE_MAP[opp_value>>20])
        if my_value>opp_value:
            print(f"Congratulations! you won {self.pot_info["paid"][1-self.pos]}!")
        elif my_value==opp_value:
            print("This game ended in a draw")
        else:
            print(f"Unfortunately you lost {self.pot_info["paid"][self.pos]} :(")
        return


class cfr_tree():
    def __init__(self,street,pos,raiseable,foldable,oppraise,allin,nextstreet, id):
        self.street=street
        self.pos=pos #0=sb, 1=bb
        self.raiseable=raiseable
        self.foldable=foldable
        self.id=id
        self.loaded=False
        self.saved=False
        row=col=0
        if self.street!=0: #0=preflop, 1=flop, 2=turn, 3=river
            row=5
        else:
            row=35
        if raiseable==False:
            col=2
            self.action={0:'fold', 1:'call'}
        elif foldable==False:
            col=4
            self.action={0:'call', 1:'raise1/2',2:'raise1',3:'allin'}
        else:
            col=5
            self.action={0:'fold', 1:'call', 2:'raise1/2',3:'raise1', 4:'allin'}
        if street!=0:       
            self.action_p=np.zeros((row, 12, col))
            self.action_p+= 1/col
            self.regret=np.zeros((row, 12, col))
            self.mixed_action=np.zeros((row, 12, col))
            self.mixed_action+= 1/col
            self.subtree=[0]*col
            self.traintime=np.zeros((row, 12))
        else:
            self.action_p=np.zeros((row, col))
            self.action_p+= 1/col
            self.regret=np.zeros((row, col))
            self.mixed_action=np.zeros((row, col))
            self.mixed_action+= 1/col
            self.subtree=[0]*col
            self.traintime=np.zeros((row))

        if raiseable==False:
            self.subtree[0]=None
            if street==3 or allin==True:
                self.subtree[1]=None
            else:
                self.subtree[1]=nextstreet
        elif foldable==False:
            if pos==0:
                self.subtree[0]=cfr_tree(street,1,True,False,True,False,nextstreet, self.id*10)
            elif street==3:
                self.subtree[0]=None
            else:
                self.subtree[0]=nextstreet #go to next street
            for i in range(1,3,1):
                self.subtree[i]=cfr_tree(street,1-pos,True,True,False,False,nextstreet, self.id*10+i)
            self.subtree[3]=cfr_tree(street,1-pos,False,True,False,True,nextstreet, self.id*10+3)
        else:
            self.subtree[0]=None
            if street==3:
                self.subtree[1]=None
            elif street==0 and pos==0 and oppraise==True:
                self.subtree[1]=cfr_tree(street,1-pos,True,False,True,False,nextstreet, self.id*10+1)
            else:
                self.subtree[1]=nextstreet
            for i in range(2,4,1):
                if oppraise==True:
                    self.subtree[i]=cfr_tree(street,1-pos,True,True,False,False,nextstreet, self.id*10+i)
                else:
                    self.subtree[i]=cfr_tree(street,1-pos,False,True,False,False,nextstreet, self.id*10+i)
            self.subtree[4]=cfr_tree(street,1-pos,False,True,False,True,nextstreet, self.id*10+4)
            
    def fit(self, pos, game_example, pot_info):
        if self.pos==0 and self.street!=0 and len(self.action_p[0][0])==4:
            pot_info=resetpotinfo(pot_info)
        if pos!=self.pos:
            cardtype=game_example["classification"][self.pos][self.street]
            p=random.random()
            action=0
            if self.street==0:
                for i in range(len(self.action_p[0])):
                    if cardtype==None:
                        print("error")
                    if p<sum(self.action_p[cardtype][j] for j in range(i+1)):
                        action=i
                        break
            else:
                state_num=getstatenum(pot_info,self.street)+game_example["prestate"][self.pos][self.street]*3
                for i in range(len(self.action_p[0][0])):
                    if p<sum(self.action_p[cardtype][state_num][j] for j in range(i+1)):
                        action=i
                        break
            new_pot_info=self.updatepotinfo(action,pot_info)
            if self.subtree[action]==None:
                if self.action[action]=='fold':
                    return new_pot_info['paid'][self.pos]
                else:
                    return new_pot_info['pot']*((1-self.pos)==game_example['winner'])-new_pot_info['paid'][1-self.pos]
            else:
                return self.subtree[action].fit(pos, game_example, new_pot_info)
        else:
            cardtype=game_example["classification"][self.pos][self.street]
            state_num=0
            if self.street!=0:
                state_num=getstatenum(pot_info,self.street)+game_example["prestate"][self.pos][self.street]*3
            col=0
            if self.street==0:
                col=len(self.action_p[0])
            else:
                col=len(self.action_p[0][0])
            utility=[0]*col
            exp_utility=0
            for i in range(col):    
                new_pot_info=self.updatepotinfo(i, pot_info)
                if self.subtree[i]==None:
                    if self.action[i]=='fold':
                        utility[i]=-new_pot_info['paid'][self.pos]
                    else:
                        utility[i]=new_pot_info['pot']*(self.pos==game_example['winner'])-new_pot_info['paid'][self.pos]
                else:
                    utility[i]=self.subtree[i].fit(pos, game_example, new_pot_info)
                if self.street==0:
                    exp_utility+=self.action_p[cardtype][i]*utility[i]
                else:
                    exp_utility+=self.action_p[cardtype][state_num][i]*utility[i]
            regret=[utility[i]-exp_utility for i in range(len(utility))]
            if self.street==0:
                self.traintime[cardtype]+=1
                t=self.traintime[cardtype]
                self.regret[cardtype]=[regret[i]+self.regret[cardtype][i] for i in range(len(regret))]
                total_pos_regret=sum( max(0,self.regret[cardtype][i]) for i in range(len(utility) ) )
                if total_pos_regret==0:
                    self.action_p[cardtype]=[1/len(utility)]*len(utility)
                else:
                    for i in range(len(utility)):
                        self.action_p[cardtype][i]=float(max(0,self.regret[cardtype][i])/total_pos_regret)
                for i in range(len(utility)):
                    self.mixed_action[cardtype][i]=float((t-1)/(t+1))*self.mixed_action[cardtype][i]+float(2/(t+1))*self.action_p[cardtype][i]
            else:
                self.traintime[cardtype][state_num]+=1
                t=self.traintime[cardtype][state_num]
                self.regret[cardtype][state_num]=[regret[i]+self.regret[cardtype][state_num][i] for i in range(len(regret))]
                total_pos_regret=sum( max(0,self.regret[cardtype][state_num][i]) for i in range(len(utility) ) )
                if total_pos_regret==0:
                    self.action_p[cardtype][state_num]=[1/len(utility)]*len(utility)
                else:  
                    for i in range(len(utility)):
                        self.action_p[cardtype][state_num][i]=float(max(0,self.regret[cardtype][state_num][i])/total_pos_regret)
                for i in range(len(utility)):
                    self.mixed_action[cardtype][state_num][i]=float((t-1)/(t+1))*self.mixed_action[cardtype][state_num][i]+float(2/(t+1))*self.action_p[cardtype][state_num][i]
            return exp_utility

    def updatepotinfo(self, action, pot_info):
        new_pot_info=pot_info_deepcopy(pot_info)
        raise_amount=0
        if self.action[action]=='fold':
            return new_pot_info
        elif self.action[action]=='call':
            pay_amount=new_pot_info['paid_cur'][1-self.pos]-new_pot_info['paid_cur'][self.pos]
            new_pot_info['paid_cur'][self.pos]+=pay_amount
            new_pot_info['paid'][self.pos]+=pay_amount
            new_pot_info['pot']+=pay_amount
            return new_pot_info
        elif self.action[action]=='raise1/2':
            raise_amount=int(new_pot_info['pot']/2)
        elif self.action[action]=='raise1':
            raise_amount=new_pot_info['pot']
        else:#allin
            raise_amount=1000-new_pot_info['paid'][1-self.pos]
        pay_amount=new_pot_info['paid_cur'][1-self.pos]-new_pot_info['paid_cur'][self.pos]+raise_amount
        new_pot_info['paid_cur'][self.pos]+=pay_amount
        new_pot_info['paid'][self.pos]+=pay_amount
        new_pot_info['pot']+=pay_amount
        new_pot_info['raise_cur'][self.pos]+=raise_amount
        return new_pot_info
    
    def tonextstate(self,action):
        for i in range(len(self.subtree)):
            if self.action[i]==action:
                return self.subtree[i]
        return None

    def chooseaction(self,cardtype, state_num):
        p=random.random()
        print('p: '+str(p))
        action=0
        if self.street==0: #preflop
            print(self.mixed_action[cardtype])
            for i in range(len(self.action_p[0])):
                if p<sum(self.mixed_action[cardtype][j] for j in range(i+1)):
                    action=i
                    break
        else:
            print(self.mixed_action[cardtype][state_num])
            for i in range(len(self.action_p[0][0])):
                if p<sum(self.mixed_action[cardtype][state_num][j] for j in range(i+1)):
                    action=i
                    break
        return self.action[action]
    def print_id(self):
        print(f"current node id={self.id}")
    
    def load(self):
        if self.loaded==True:
            return
        values = loaded[str(self.id)].item()
        self.action_p[:]=values["action"]
        self.regret[:]=values["regret"]
        self.mixed_action[:]=values["mixedaction"]
        self.traintime[:]=values["traintime"]
        self.loaded=True

        for child in self.subtree:
            if child!=None:
                child.load()
        return
    def save(self):
        if self.saved==True:
            return
        data[self.id] = {
            "action": self.action_p,
            "regret": self.regret,
            "mixedaction": self.mixed_action,
            "traintime": self.traintime
        }

        self.saved=True
        for child in self.subtree:
            if child!=None:
                child.save()
    
def resetpotinfo(pot_info):
    pot_info['raise_prev']=[pot_info['raise_prev'][0]+pot_info['raise_cur'][0],pot_info['raise_prev'][1]+pot_info['raise_cur'][1]]
    pot_info['raise_cur']=[0,0]
    pot_info["paid_cur"]=[0,0]
    return pot_info

def getstatenum(pot_info,street):
    raise_pre=int((pot_info['raise_prev'][0]<=2*pot_info['raise_prev'][1]) + (2*pot_info['raise_prev'][0]<pot_info['raise_prev'][1]) )
    return raise_pre
            
def pot_info_deepcopy(pot_info):
    new_pot_info={"pot":pot_info["pot"],
                  "paid":[pot_info["paid"][0],pot_info["paid"][1]],
                  'paid_cur':[pot_info["paid_cur"][0],pot_info["paid_cur"][1]],
                  'raise_prev':[pot_info["raise_prev"][0],pot_info["raise_prev"][1]],
                  'raise_cur':[pot_info["raise_cur"][0],pot_info["raise_cur"][1]],}
    return new_pot_info

def generate_gamexample():
    deck=full_deck[:]
    random.shuffle(deck)
    hand=[deck[:2],deck[2:4]]
    board=deck[4:9]
    result={}
    result["classification"]=[[0]*4 for i in range(2)]
    result["prestate"]=[[0]*4 for i in range(2)]
    hand_id=[[hand[0][0].to_id()-1,hand[0][1].to_id()-1],[hand[1][0].to_id()-1,hand[1][1].to_id()-1]]
    hand_num=[[hand_id[0][0]%13+1,hand_id[0][1]%13+1],[hand_id[1][0]%13+1,hand_id[1][1]%13+1]]
    for i in range(2):
        for j in range(2):
            if(hand_num[i][j]==1):
                hand_num[i][j]=14
    for i in range(2):
        winrate=0
        if int(hand_id[i][0]/13)==int(hand_id[i][1]/13):
            result["classification"][i][0]=preflop_winrate.classification(max(hand_num[i][0],hand_num[i][1]),min(hand_num[i][0],hand_num[i][1]))
            winrate=preflop_winrate.lookup(max(hand_num[i][0],hand_num[i][1]),min(hand_num[i][0],hand_num[i][1]))
        else:
            result["classification"][i][0]=preflop_winrate.classification(min(hand_num[i][0],hand_num[i][1]),max(hand_num[i][0],hand_num[i][1]))
            winrate=preflop_winrate.lookup(min(hand_num[i][0],hand_num[i][1]),max(hand_num[i][0],hand_num[i][1]))
        result["prestate"][i][1]=min(int(winrate*4),3)
    for i in range(2):
        for j in range(1,4,1):
            winrate=winrate_estimate.estimate(hand[i],board[:j+2])
            result["classification"][i][j]=min(int(winrate*5),4)
            if j<3:
                result["prestate"][i][j+1]=min(int(winrate*4),3)
    dif=HandEvaluator.eval_hand(hand[0],board)-HandEvaluator.eval_hand(hand[1],board)
    if dif>0:
        result["winner"]=0
    elif dif<0:
        result["winner"]=1
    else:
        result["winner"]=0.5
    return result    


def generate_example(num_opponent_samples=100, num_com=3):
    deck = full_deck[:]
    random.shuffle(deck)
    
    hand = deck[:2]
    board = deck[2:2+num_com]

    wins = ties = 0
    opp_deck = [card for card in full_deck if card not in hand + board]
    for _ in range(num_opponent_samples):
        random.shuffle(opp_deck)
        opp_hand = opp_deck[:2]

        if num_com < 5:
            remaining_board = opp_deck[2:2 + (5 - num_com)]
            full_board = board + remaining_board
        else:
            full_board = board

        opp_score = HandEvaluator.eval_hand(opp_hand, full_board)
        my_score_full = HandEvaluator.eval_hand(hand, full_board)

        if my_score_full > opp_score:
            wins += 1
        elif my_score_full == opp_score:
            ties += 1

    win_rate = (wins + ties * 0.5) / num_opponent_samples
    input_vector = encode_cards_vector(hand, board)
    return input_vector, win_rate


def setup_ai():
    return MyPlayer()

