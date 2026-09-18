(define (domain domain_pddl)
    (:requirements :negative-preconditions :typing)
    (:types
        locatable - object
        location - object
        robot - locatable
        item - locatable
        device - item
        furniture - locatable
        residue - item
        car - furniture
        vacuum - device
        dust - residue
        floor - furniture
    )
    (:predicates
        (at ?e - locatable ?l - location)
        (on_top ?top - item ?bottom - locatable)
        (holding ?a - robot ?o - item)
        (robot_free ?r - robot)
        (covered ?o - locatable ?s - residue)
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
    :parameters (?r - robot ?o - item ?l - location ?support - locatable)
    :precondition
        (and
            (at ?r ?l)
            (at ?o ?l)
            (on_top ?o ?support)
            (robot_free ?r)
        )
    :effect
        (and
            (holding ?r ?o)
            (not (robot_free ?r))
            (not (on_top ?o ?support))
        )
)

(:action clean
    :parameters (?r - robot ?v - vacuum ?o - locatable ?d - dust ?l - location)
    :precondition
        (and
            (at ?r ?l)
            (holding ?r ?v)
            (covered ?o ?d)
        )
    :effect
        (and
            (not (covered ?o ?d))
        )
)
)
