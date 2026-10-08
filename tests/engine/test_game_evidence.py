"""Cases the real game showed, as fixed seeds and what each produced.

They come from balatro-ai's stage 0 (``docs/redesign/etapa-0-resultados.md``
in that project): the PC game (Steamodded, BalatroBot) and the PS5 (vanilla
1.0.1o) were played on these seeds and the results noted.  Rounds are won by
setting the blind's target to 1 before a play: these cases are about the run's
other streams, which a round's score does not touch.
"""

from __future__ import annotations

from collections import Counter

import pytest

from jackdaw.engine.actions import (
    CashOut,
    NextRound,
    PlayHand,
    RerollBoss,
    SelectBlind,
    SkipBlind,
    UseConsumable,
)
from jackdaw.engine.card_factory import create_consumable, create_playing_card
from jackdaw.engine.data.enums import Rank, Suit
from jackdaw.engine.data.hands import HandType
from jackdaw.engine.data.prototypes import BLINDS
from jackdaw.engine.game import IllegalActionError, step
from jackdaw.engine.run_init import initialize_run
from jackdaw.engine.tags import HAND_PICK_ORDER, hand_pick_pool

WHITE, GOLD = 1, 8


def _win(gs: dict) -> None:
    """The blind on offer selected, won with five cards, and cashed out."""
    if gs["phase"] == "blind_select":
        step(gs, SelectBlind())
    gs["blind"].chips = 1
    step(gs, PlayHand(card_indices=tuple(range(min(5, len(gs["hand"]))))))
    step(gs, CashOut())


def _boss(gs: dict) -> str:
    return BLINDS[gs["round_resets"]["blind_choices"]["Boss"]].name


def _cards(cards) -> Counter:
    return Counter((c.base.suit.value, c.base.rank.value, c.center_key) for c in cards)


def _use(gs: dict, key: str) -> None:
    gs["consumables"].append(create_consumable(key))
    step(gs, UseConsumable(card_index=len(gs["consumables"]) - 1, target_indices=None))


# -- Grim: the suit of each Ace is the next 'grim_create' draw (PC) -----------


GRIM = {
    "VERIFYAA": ([("Clubs", "Ace", "m_mult"), ("Hearts", "Ace", "m_lucky")], ("Diamonds", "10")),
    "VERIFYBB": ([("Spades", "Ace", "m_glass")] * 2, ("Diamonds", "King")),
}


@pytest.mark.parametrize(
    ("seed", "created", "destroyed"), [(seed, *found) for seed, found in GRIM.items()]
)
def test_grim_creates_the_aces_the_game_created(seed, created, destroyed):
    gs = initialize_run("b_red", GOLD, seed)
    step(gs, SelectBlind())
    before = _cards(gs["hand"])
    _use(gs, "c_grim")
    after = _cards(gs["hand"])
    assert sorted((after - before).elements()) == sorted(created)
    assert [card[:2] for card in (before - after).elements()] == [destroyed]


# -- To Do List and the Orbital Tag: the hands in the game's order (PS5) ------


def test_the_hands_are_picked_from_strongest_first():
    assert HAND_PICK_ORDER[0] == HandType.FLUSH_FIVE
    assert HAND_PICK_ORDER[-1] == HandType.HIGH_CARD
    assert hand_pick_pool({}) == [
        "Straight Flush", "Four of a Kind", "Full House", "Flush", "Straight",
        "Three of a Kind", "Two Pair", "Pair", "High Card",
    ]  # fmt: skip


def test_to_do_list_in_the_first_shop_of_bqzsvsac_wants_a_straight_flush():
    gs = initialize_run("b_red", WHITE, "BQZSVSAC")
    _win(gs)
    todo = next(card for card in gs["shop_cards"] if card.center_key == "j_todo_list")
    assert todo.ability["to_do_poker_hand"] == "Straight Flush"


def test_the_orbital_tag_of_dhxxvbvv_ante_2_levels_up_full_house():
    gs = initialize_run("b_red", WHITE, "DHXXVBVV")
    for _ in range(3):  # ante 1: three 'orbital' draws, one per blind shown
        _win(gs)
        step(gs, NextRound())
    assert gs["round_resets"]["blind_tags"]["Small"] == "tag_orbital"
    step(gs, SkipBlind())
    assert gs["hand_levels"].get_state(HandType.FULL_HOUSE).level == 4


def test_three_orbital_draws_per_ante_whatever_the_tags():
    gs = initialize_run("b_red", WHITE, "DHXXVBVV")
    assert set(gs["orbital_choices"][1]) == {"Small", "Big", "Boss"}


# -- The boss reroll: the next draw of the 'boss' stream (PS5 and PC) ----------


def test_the_boss_tag_of_fwqqgdzg_rerolls_the_head_into_the_hook():
    gs = initialize_run("b_red", WHITE, "FWQQGDZG")
    assert _boss(gs) == "The Head"
    step(gs, SkipBlind())  # the Small Blind's Boss Tag
    assert _boss(gs) == "The Hook"
    for _ in range(2):  # the Big Blind and the boss
        _win(gs)
        step(gs, NextRound())
    assert gs["round_resets"]["ante"] == 2 and _boss(gs) == "The Psychic"


def test_directors_cut_rerolls_the_boss_as_the_boss_tag_does():
    gs = initialize_run("b_red", WHITE, "FWQQGDZG")
    gs["used_vouchers"]["v_directors_cut"] = True
    gs["dollars"] = 12
    step(gs, RerollBoss())
    assert _boss(gs) == "The Hook"
    assert gs["dollars"] == 2 and gs["round_resets"]["boss_rerolled"] is True
    gs["dollars"] = 50
    with pytest.raises(IllegalActionError):  # Director's Cut: once per ante
        step(gs, RerollBoss())


def test_retcon_rerolls_again_and_each_reroll_costs_ten():
    gs = initialize_run("b_red", WHITE, "FWQQGDZG")
    gs["used_vouchers"]["v_retcon"] = True
    gs["dollars"] = 20
    step(gs, RerollBoss())
    step(gs, RerollBoss())
    assert gs["dollars"] == 0
    with pytest.raises(IllegalActionError):  # no $10 left
        step(gs, RerollBoss())


def test_no_reroll_without_the_vouchers():
    gs = initialize_run("b_red", WHITE, "FWQQGDZG")
    gs["dollars"] = 50
    with pytest.raises(IllegalActionError):
        step(gs, RerollBoss())


# -- The two bugs the replay of a recorded game found ------------------------


def test_black_hole_is_not_the_last_tarot_or_planet_used():
    gs = initialize_run("b_red", WHITE, "BLACKHOLE")
    step(gs, SelectBlind())
    gs["last_tarot_planet"] = "c_mars"
    _use(gs, "c_black_hole")
    assert gs["last_tarot_planet"] == "c_mars"


def test_a_held_blue_seal_makes_one_planet_however_the_hand_is_ordered():
    gs = initialize_run("b_red", WHITE, "BLUESEAL")
    step(gs, SelectBlind())
    # Lowest card first: creating the planet sorts the hand, and the Blue Seal
    # card moves behind the loop that is reading the hand.
    gs["hand"].sort(key=lambda card: card.get_nominal())
    gs["hand"][0].set_seal("Blue")
    gs["blind"].chips = 1
    step(gs, PlayHand(card_indices=(len(gs["hand"]) - 1,)))  # High Card
    assert [card.center_key for card in gs["consumables"]] == ["c_pluto"]


# -- Secret hands: visible once played, not once levelled up (PC) -------------


def test_a_black_hole_does_not_add_the_secret_hands_to_the_pool():
    gs = initialize_run("b_red", GOLD, "VERIFYCC")
    _win(gs)
    _use(gs, "c_black_hole")
    assert gs["hand_levels"].get_state(HandType.FIVE_OF_A_KIND).level == 2
    assert len(hand_pick_pool(gs)) == 9


def test_a_played_five_of_a_kind_joins_the_pool():
    gs = initialize_run("b_red", GOLD, "VERIFYCC")
    step(gs, SelectBlind())
    for suit in (Suit.SPADES, Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS, Suit.SPADES):
        gs["hand"].append(create_playing_card(suit, Rank.ACE))  # five Aces
    gs["blind"].chips = 1
    step(gs, PlayHand(card_indices=tuple(range(len(gs["hand"]) - 5, len(gs["hand"])))))
    assert gs["hand_levels"].get_state(HandType.FIVE_OF_A_KIND).played == 1
    assert hand_pick_pool(gs)[0] == "Five of a Kind" and len(hand_pick_pool(gs)) == 10
