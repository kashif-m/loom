'use client';

import { useEffect, useState, useRef } from 'react';
import Link from 'next/link';
import { Activity, Pause, Play } from 'lucide-react';
import Navigation from '../../components/Navigation';
import PageHeader from '../../components/PageHeader';
import { FeedEvent } from '../../lib/types';
import { createEventSource } from '../../lib/api';
import { formatDistanceToNow } from 'date-fns';

export default function ActivityFeed() {
  const [events, setEvents] = useState<FeedEvent[]>([]);
  const [isPaused, setIsPaused] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const eventSourceRef = useRef<EventSource | null>(null);
  const queuedEvents = useRef<FeedEvent[]>([]);

  useEffect(() => {
    const es = createEventSource();
    eventSourceRef.current = es;

    es.onopen = () => {
      setIsConnected(true);
    };

    es.onerror = () => {
      setIsConnected(false);
    };

    es.addEventListener('task_event', (e: MessageEvent) => {
      const data = JSON.parse(e.data);
      if (isPaused) {
        queuedEvents.current.push(data);
      } else {
        setEvents(prev => [data, ...prev].slice(0, 200));
      }
    });

    es.addEventListener('keepalive', () => {
      // Keepalive received
    });

    return () => {
      es.close();
    };
  }, [isPaused]);

  const togglePause = () => {
    if (isPaused) {
      // Resume - add queued events
      setEvents(prev => [...queuedEvents.current, ...prev].slice(0, 200));
      queuedEvents.current = [];
    }
    setIsPaused(!isPaused);
  };

  const getEventColor = (type: string) => {
    if (type.includes('escalated')) return 'text-red-600';
    if (type.includes('completed')) return 'text-green-600';
    if (type.includes('blocked')) return 'text-amber-600';
    return 'text-blue-600';
  };

  return (
    <div>
      <Navigation />
      
      <main className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="flex items-center justify-between mb-8">
          <PageHeader 
            title="Activity Feed" 
            subtitle="Live view of agent activity"
          />
          <div className="flex items-center gap-4">
            <div className={`flex items-center gap-2 text-sm ${isConnected ? 'text-green-600' : 'text-red-600'}`}>
              <span className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-600' : 'bg-red-600'}`} />
              {isConnected ? 'Live' : 'Disconnected'}
            </div>
            <button
              onClick={togglePause}
              className="inline-flex items-center px-3 py-2 border border-gray-300 text-sm font-medium rounded-md bg-white hover:bg-gray-50"
            >
              {isPaused ? <Play className="w-4 h-4 mr-2" /> : <Pause className="w-4 h-4 mr-2" />}
              {isPaused ? 'Resume' : 'Pause'}
            </button>
          </div>
        </div>

        {isPaused && queuedEvents.current.length > 0 && (
          <div className="mb-4 bg-amber-50 border border-amber-200 rounded-md p-3 text-sm text-amber-800">
            {queuedEvents.current.length} new events queued
          </div>
        )}

        <div className="bg-white shadow rounded-lg">
          <div className="overflow-hidden">
            {events.length === 0 ? (
              <div className="p-8 text-center text-gray-500">
                <Activity className="h-12 w-12 mx-auto mb-4 text-gray-300" />
                <p>Waiting for activity...</p>
                <p className="text-sm mt-1">Events will appear here in real-time</p>
              </div>
            ) : (
              <div className="divide-y divide-gray-200">
                {events.map((event) => (
                  <div key={event.id} className="px-6 py-4 hover:bg-gray-50">
                    <div className="flex items-start">
                      <div className="flex-shrink-0">
                        <div className={`h-2 w-2 rounded-full mt-2 ${getEventColor(event.type)}`} />
                      </div>
                      <div className="ml-3 flex-1">
                        <p className="text-sm text-gray-900">
                          {event.label}
                        </p>
                        <div className="mt-1 flex items-center gap-3 text-xs text-gray-500">
                          <Link 
                            href={`/tasks/${event.task_id}`}
                            className="font-mono text-amber-600 hover:text-amber-900"
                          >
                            {event.task_id.substring(0, 8)}...
                          </Link>
                          {event.agent_id && (
                            <span>{event.agent_id}</span>
                          )}
                          <span>
                            {formatDistanceToNow(new Date(event.timestamp), { addSuffix: true })}
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
