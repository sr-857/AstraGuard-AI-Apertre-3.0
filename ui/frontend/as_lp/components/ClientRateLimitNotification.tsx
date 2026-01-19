"use client"

import { useState, useEffect } from "react"
import { RateLimitNotification } from "./rate-limit-notification"

export function ClientRateLimitNotification() {
    const [mounted, setMounted] = useState(false)

    useEffect(() => {
        setMounted(true)
    }, [])

    if (!mounted) return null

    return <RateLimitNotification />
}
