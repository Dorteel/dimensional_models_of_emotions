(define (domain domain_pddl)
    (:requirements :negative-preconditions :typing)
    (:types
        locatable - object
        location - object
        robot - locatable
        item - locatable
        container - item
        furniture - locatable
        car - container
        briefcase - item
        satchel - item
        sofa - furniture
    )
    (:predicates
        (at ?e - locatable ?l - location)
        (in ?o - item ?c - container)
        (next_to ?a - item ?b - locatable)
        (on_top ?top - item ?bottom - locatable)
        (holding ?a - robot ?o - item)
        (robot_free ?r - robot)
    )

    ;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;; ACTION ;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;

    (:action drive
    :parameters (?r - robot ?c - car ?from - location ?to - location)
    :precondition
        (and
            (at ?r ?from)
            (at ?c ?from)
        )
    :effect
        (and
            (not (at ?r ?from))
            (not (at ?c ?from))
            (at ?r ?to)
            (at ?c ?to)
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
            (robot_free ?r)
            (not (holding ?r ?o))
        )
)
)
