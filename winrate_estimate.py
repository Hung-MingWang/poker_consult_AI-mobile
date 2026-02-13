import my_evaluator as HandEvaluator
from game.card import Card
import random

suits = [2,4,8,16]
ranks = list(range(2, 15)) 
full_deck = [Card(suit, rank) for suit in suits for rank in ranks]


def generate_example(num_opponent_samples=1000, hand=None, board=None):
    deck = full_deck[:]
    random.shuffle(deck)

    num_com=len(board)
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
    return win_rate

def estimate(hole_card=None, com=None):
    return generate_example(hand=hole_card, board=com)

