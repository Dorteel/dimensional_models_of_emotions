(define (domain domain_pddl)
    (:requirements :negative-preconditions :typing)
    (:types
        locatable - object
        location - object
        robot - locatable
        item - locatable
        container - item
        device - item
        furniture - locatable
        bath_towel - item
        residue - item
        dirt - residue
        washer - device
        clothes_dryer - device
        detergent_bottle - container
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

(:action clean
    :parameters (?r - robot ?o - locatable ?s - residue ?l - location)
    :precondition
        (and
            (at ?r ?l)
            (at ?o ?l)
            (robot_free ?r)
            (covered ?o ?s)
        )
    :effect
        (and
            (not (covered ?o ?s))
        )
)
)
