import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './UsageTimer.css';
import { config } from '../config';

const API_BASE = `${config.API_URL}/api`;

interface UsageStats {
  remaining_seconds: number;
  daily_limit_seconds: number;
  can_run: boolean;
}

export function UsageTimer() {
  const [stats, setStats] = useState<UsageStats>({
    remaining_seconds: 300,
    daily_limit_seconds: 300,
    can_run: true
  });


  useEffect(() => {
    // PERFORMANCE: Delay polling until after initial page load
    const startPolling = setTimeout(() => {
      const fetchUsage = async () => {
        try {
const res = await fetch(`${API_BASE}/simulation/usage`);
          const data = await res.json();
          setStats(data);
        } catch (error) {
          console.error('Failed to fetch usage stats:', error);
        }
      };

      fetchUsage(); // Initial fetch
      const interval = setInterval(fetchUsage, 1000); // Poll every 1 second

      return () => clearInterval(interval);
    }, 2000); // Wait 2 seconds before starting

    return () => clearTimeout(startPolling);
  }, []);

  const remaining = Math.floor(stats.remaining_seconds);
  const minutes = Math.floor(remaining / 60);
  const seconds = remaining % 60;
  const percentage = (stats.remaining_seconds / stats.daily_limit_seconds) * 100;

  return (
    <div 
      className="usage-timer"
      title="5 minutes per day to contribute to the learning system (Demo period for judges)"
    >
      <span className="timer-icon">⏱️</span>
      <span className="timer-text">
        {minutes}:{seconds.toString().padStart(2, '0')}
      </span>
    </div>
  );
}
