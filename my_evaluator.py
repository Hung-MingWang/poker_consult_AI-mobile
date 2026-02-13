from game.card import Card
import random

def eval_hand(hole, community):
    rank_list=[0]*15
    suit_list=[0]*4
    id_list=[]
    for card in hole+community:
        card_id=card.to_id()
        suit_list[(int)((card_id-1)/13)]+=1
        rank_list[(card_id-1)%13 +1]+=1
        id_list.append(card_id)
    rank_list[14]=rank_list[1]
    if max(suit_list[i] for i in range(4))>=5: #flush
        suit=0
        while True:
            if suit_list[suit]>=5:
                break
            suit+=1
        rank_list_of_suit=[0]*15
        for card_id in id_list:
            if (int)((card_id-1)/13)==suit:
                rank_list_of_suit[(card_id-1)%13+1]+=1
        rank_list_of_suit[14]=rank_list_of_suit[1]
        is_straight=False
        straight_rank=None
        for i in range(14,4,-1):
            is_straight=True
            for j in range(0,5,1):
                if rank_list_of_suit[i-j]==0:
                    is_straight=False
                    break
            if is_straight==True:
                straight_rank=i
                break
        if is_straight:
            return 1<<28+straight_rank
        result=[]
        result_count=0
        for i in range(14,1,-1):
            if rank_list_of_suit[i]==1:
                result.append(i)
                result_count+=1
                if result_count==5:
                    break
        return (1<<25) + sum(result[i]<<(16-4*i) for i in range(5))
    is_straight=False
    straight_rank=None
    for i in range(14,4,-1):
        is_straight=True
        for j in range(0,5,1):
            if rank_list[i-j]==0:
                is_straight=False
                break
        if is_straight==True:
            straight_rank=i
            break 
    if is_straight:
        return (1<<24)+straight_rank
    max_occur=max(rank_list[i] for i in range(15))
    if max_occur==4: #fourcard
        four_rank=None
        single_rank=None
        for i in range(14,1,-1):
            if rank_list[i]==4:
                four_rank=i
                if single_rank!=None:
                    break
            elif rank_list[i]>=1 and single_rank==None:
                single_rank=i
                if four_rank!=None:
                    break
        return (1<<27) + (four_rank<<4) + single_rank
    elif max_occur==3: #fullhorse or threecard
        three_rank=None
        two_rank=None
        for i in range(14,1,-1):
            if rank_list[i]==3 and three_rank==None:
                three_rank=i
                if two_rank!=None:
                    break
            elif rank_list[i]>=2 and two_rank==None:
                two_rank=i
                if three_rank!=None:
                    break
        if two_rank!=None:
            return (1<<26) + (three_rank<<4) + two_rank
        single_rank=[]
        order=0
        for i in range(14,1,-1):
            if rank_list[i]==1:
                single_rank.append(i)
                order+=1
                if order==2:
                    break
        return (1<<23) + (three_rank<<8) + (single_rank[0]<<4) + single_rank[1]
    elif max_occur==2: #twopair or onepair
        two_rank=[]
        single_rank=[]
        order_2=0
        for i in range(14,1,-1):
            if rank_list[i]==2 and order_2<2:
                two_rank.append(i)
                order_2+=1
            elif rank_list[i]>=1:
                single_rank.append(i)
        if order_2==2:
            return (1<<22) + (two_rank[0]<<8) + (two_rank[1]<<4) + single_rank[0]
        else:
            return (1<<21) + (two_rank[0]<<12) + (single_rank[0]<<8) + (single_rank[1]<<4) + single_rank[2]
    else:
        single_rank=[]
        order=0
        for i in range(14,1,-1):
            if rank_list[i]==1:
                single_rank.append(i)
                order+=1
                if order>=5:
                    break
        return (1<<20) + sum(single_rank[i]<<(16-4*i) for i in range(5))


suits = [2,4,8,16]
ranks = list(range(2, 15)) 
full_deck = [Card(suit, rank) for suit in suits for rank in ranks]



                


