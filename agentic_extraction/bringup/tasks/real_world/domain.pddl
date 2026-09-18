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
        banana - food
        pear - food
        apple - food
        orange - food
        plate - item
        bowl - container
        table - furniture
    )
    (:predicates
        (at ?e - locatable ?l - location)
        (on_top ?top - item ?bottom - locatable)
        (in ?o - item ?c - container)
        (holding ?a - robot ?o - item)
        (robot_free ?r - robot)
    )

    ;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;; ACTION ;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;

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
            (not (at ?o ?l))
            (not (robot_free ?r))
            (holding ?r ?o)
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
)
