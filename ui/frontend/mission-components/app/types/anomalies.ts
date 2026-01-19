export interface AnomalyEvent {
  id: string;
  satellite: string;
  severity: 'Critical' | 'Warning' | 'Info';
  metric: string;
  value: string;
  timestamp: string;
  acknowledged: boolean;
}
