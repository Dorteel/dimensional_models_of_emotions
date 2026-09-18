(define (domain domain_pddl)
    (:requirements :negative-preconditions :typing)
    (:types
        locatable - object
        location - object
        robot - locatable
        item - locatable
        furniture - locatable
        garment - item
        short_pants - garment
        blouse - garment
        trouser - garment
        dress - garment
        brassiere - garment
        tank_top - garment
        bed - furniture
    )
    (:predicates
        (at ?e - locatable ?l - location)
        (on_top ?top - item ?bottom - locatable)
        (next_to ?a - item ?b - locatable)
        (under ?a - item ?b - locatable)
        (touching ?a - item ?b - locatable)
        (attached ?a - item ?b - locatable)
        (draped ?a - item ?b - locatable)
        (holding ?a - robot ?o - item)
        (robot_free ?r - robot)
        (covered ?o - locatable ?s - item)
        (folded ?o - item)
        (unfolded ?o - item)
        (hot ?o - locatable)
        (broken ?o - item)
        (on_fire ?o - item)
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

(:action move
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
            (holding ?r ?o)
            (not (robot_free ?r))
            (not (at ?o ?l))
        )
)

(:action place
    :parameters (?r - robot ?o - item ?l - location)
    :precondition
        (and
            (at ?r ?l)
            (holding ?r ?o)
        )
    :effect
        (and
            (at ?o ?l)
            (robot_free ?r)
            (not (holding ?r ?o))
        )
)

(:action place_in_container
    :parameters (?r - robot ?o - item ?c - locatable ?l - location)
    :precondition
        (and
            (at ?r ?l)
            (holding ?r ?o)
            (at ?c ?l)
        )
    :effect
        (and
            (covered ?c ?o)
            (robot_free ?r)
            (not (holding ?r ?o))
        )
)

(:action stack
    :parameters (?r - robot ?top - item ?bottom - locatable ?l - location)
    :precondition
        (and
            (at ?r ?l)
            (holding ?r ?top)
            (at ?bottom ?l)
        )
    :effect
        (and
            (on_top ?top ?bottom)
            (robot_free ?r)
            (not (holding ?r ?top))
        )
)

(:action unstack
    :parameters (?r - robot ?top - item ?bottom - locatable ?l - location)
    :precondition
        (and
            (at ?r ?l)
            (robot_free ?r)
            (on_top ?top ?bottom)
            (at ?bottom ?l)
        )
    :effect
        (and
            (holding ?r ?top)
            (not (robot_free ?r))
            (not (on_top ?top ?bottom))
        )
)

(:action open
    :parameters (?r - robot ?o - item ?l - location)
    :precondition
        (and
            (at ?r ?l)
            (at ?o ?l)
        )
    :effect
        (and
            (unfolded ?o)
            (not (folded ?o))
        )
)

(:action close
    :parameters (?r - robot ?o - item ?l - location)
    :precondition
        (and
            (at ?r ?l)
            (at ?o ?l)
        )
    :effect
        (and
            (folded ?o)
            (not (unfolded ?o))
        )
)

(:action push
    :parameters (?r - robot ?o - item ?from - location ?to - location)
    :precondition
        (and
            (at ?r ?from)
            (at ?o ?from)
        )
    :effect
        (and
            (not (at ?r ?from))
            (at ?r ?to)
            (not (at ?o ?from))
            (at ?o ?to)
        )
)

(:action pull
    :parameters (?r - robot ?o - item ?from - location ?to - location)
    :precondition
        (and
            (at ?r ?from)
            (at ?o ?from)
        )
    :effect
        (and
            (not (at ?r ?from))
            (at ?r ?to)
            (not (at ?o ?from))
            (at ?o ?to)
        )
)

(:action pour
    :parameters (?r - robot ?source - item ?target - locatable ?l - location)
    :precondition
        (and
            (at ?r ?l)
            (holding ?r ?source)
            (at ?target ?l)
        )
    :effect
        (and
            (touching ?source ?target)
        )
)

(:action clean
    :parameters (?r - robot ?o - item ?l - location)
    :precondition
        (and
            (at ?r ?l)
            (at ?o ?l)
        )
    :effect
        (and
            (not (broken ?o))
            (not (on_fire ?o))
        )
)

(:action fold
    :parameters (?r - robot ?o - item ?l - location)
    :precondition
        (and
            (at ?r ?l)
            (at ?o ?l)
            (unfolded ?o)
        )
    :effect
        (and
            (folded ?o)
            (not (unfolded ?o))
        )
)

(:action unfold
    :parameters (?r - robot ?o - item ?l - location)
    :precondition
        (and
            (at ?r ?l)
            (at ?o ?l)
            (folded ?o)
        )
    :effect
        (and
            (unfolded ?o)
            (not (folded ?o))
        )
)
)
