(define (domain domain_pddl)
    (:requirements :negative-preconditions :typing)
    (:types
        locatable - object
        location - object
        robot - locatable
        item - locatable
        container - item
        furniture - locatable
        pitcher - container
        countertop - furniture
        box_of_cream - item
        cabinet - container
        napkin - item
        breakfast_table - furniture
        bowl - container
        teaspoon - item
        electric_refrigerator - container
        floor - furniture
    )
    (:predicates
        (at ?e - locatable ?l - location)
        (in ?o - item ?c - container)
        (on_top ?top - item ?bottom - locatable)
        (next_to ?a - item ?b - locatable)
        (under ?a - item ?b - locatable)
        (touching ?a - item ?b - locatable)
        (attached ?a - item ?b - locatable)
        (draped ?a - item ?b - locatable)
        (holding ?a - robot ?o - item)
        (robot_free ?r - robot)
        (covered ?o - locatable ?s - item)
        (open ?t - container)
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
            (in ?o ?c)
            (robot_free ?r)
            (not (holding ?r ?o))
        )
)

(:action stack
    :parameters (?r - robot ?top - item ?bottom - locatable ?l - location)
    :precondition
        (and
            (at ?r ?l)
            (at ?bottom ?l)
            (holding ?r ?top)
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
            (at ?bottom ?l)
            (on_top ?top ?bottom)
            (robot_free ?r)
        )
    :effect
        (and
            (holding ?r ?top)
            (not (robot_free ?r))
            (not (on_top ?top ?bottom))
        )
)

(:action open
    :parameters (?r - robot ?c - container ?l - location)
    :precondition
        (and
            (at ?r ?l)
            (at ?c ?l)
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

(:action push
    :parameters (?r - robot ?o - item ?from - location ?to - location)
    :precondition
        (and
            (at ?r ?from)
            (at ?o ?from)
        )
    :effect
        (and
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
            (not (at ?o ?from))
            (at ?o ?to)
        )
)

(:action pour
    :parameters (?r - robot ?p - pitcher ?target - container ?l - location)
    :precondition
        (and
            (at ?r ?l)
            (at ?p ?l)
            (at ?target ?l)
            (holding ?r ?p)
            (open ?target)
        )
    :effect
        (and
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
        )
)

(:action fold
    :parameters (?r - robot ?o - item ?l - location)
    :precondition
        (and
            (at ?r ?l)
            (holding ?r ?o)
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
            (holding ?r ?o)
            (folded ?o)
        )
    :effect
        (and
            (unfolded ?o)
            (not (folded ?o))
        )
)
)
