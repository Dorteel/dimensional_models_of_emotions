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
        cupcake - food
        plate - item
        tablefork - item
        table_knife - item
        breakfast_table - furniture
        sink - furniture
        cabinet - container
        electric_refrigerator - container
    )
    (:predicates
        (at ?e - locatable ?l - location)
        (in ?o - item ?c - container)
        (on_top ?top - item ?bottom - locatable)
        (next_to ?a - locatable ?b - locatable)
        (holding ?a - robot ?o - item)
        (robot_free ?r - robot)
        (open ?c - container)
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
            (holding ?r ?o)
            (not (robot_free ?r))
        )
)

(:action place
    :parameters (?r - robot ?o - item ?b - locatable ?l - location)
    :precondition
        (and
            (at ?r ?l)
            (at ?b ?l)
            (holding ?r ?o)
        )
    :effect
        (and
            (on_top ?o ?b)
            (at ?o ?l)
            (not (holding ?r ?o))
            (robot_free ?r)
        )
)

(:action place_next_to
    :parameters (?r - robot ?o - item ?b - locatable ?l - location)
    :precondition
        (and
            (at ?r ?l)
            (at ?b ?l)
            (holding ?r ?o)
        )
    :effect
        (and
            (next_to ?o ?b)
            (at ?o ?l)
            (not (holding ?r ?o))
            (robot_free ?r)
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
)
