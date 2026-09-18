(define (domain domain_pddl)
    (:requirements :negative-preconditions :typing)
    (:types
        locatable - object
        location - object
        robot - locatable
        item - locatable
        container - item
        food - item
        furniture - locatable
        sour_bread - food
        sack - container
        box_of_corn_flakes - food
        cup_of_yogurt - food
        egg - food
        electric_refrigerator - container
        cabinet - container
        floor - furniture
    )
    (:predicates
        (at ?e - locatable ?l - location)
        (in ?o - item ?c - container)
        (on_top ?top - item ?bottom - locatable)
        (holding ?a - robot ?o - item)
        (robot_free ?r - robot)
        (open ?t - container)
    )

    ;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;; ACTION ;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;

    (:action drive
    :parameters (?r - robot ?from - location ?to - location)
    :precondition
        (and
            (at ?r ?from)
        )
    :effect
        (and
            (not (at ?r ?from))
            (at ?r ?to)
        )
)

(:action pick
    :parameters (?r - robot ?o - item ?l - location)
    :precondition
        (and
            (at ?r ?l)
            (at ?o ?l)
            (robot_free ?r)
        )
    :effect
        (and
            (not (at ?o ?l))
            (not (robot_free ?r))
            (holding ?r ?o)
        )
)

(:action place_in_container
    :parameters (?r - robot ?o - item ?c - container ?l - location)
    :precondition
        (and
            (at ?r ?l)
            (at ?c ?l)
            (holding ?r ?o)
            (open ?c)
        )
    :effect
        (and
            (not (holding ?r ?o))
            (robot_free ?r)
            (in ?o ?c)
        )
)

(:action open
    :parameters (?r - robot ?c - container ?l - location)
    :precondition
        (and
            (at ?r ?l)
            (at ?c ?l)
            (not (open ?c))
        )
    :effect
        (and
            (open ?c)
        )
)

(:action close
    :parameters (?r - robot ?c - container ?l - location)
    :precondition
        (and
            (at ?r ?l)
            (at ?c ?l)
            (open ?c)
        )
    :effect
        (and
            (not (open ?c))
        )
)
)
