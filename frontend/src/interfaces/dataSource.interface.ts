export interface DataSource {
    id?: string; 
    name: string;
    source_type: string;
    connection_data: string;
    is_active: number;
  }