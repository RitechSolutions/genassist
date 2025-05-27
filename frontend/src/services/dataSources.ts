import { apiRequest } from "@/config/api";
import { DataSource } from "@/interfaces/dataSource.interface";

export const getAllDataSources = async (): Promise<DataSource[]> => {
  try {
    return await apiRequest<DataSource[]>("GET", "datasources/");
  } catch (error) {
    console.error("Error fetching data sources:", error);
    throw error;
  }
};

export const getDataSource = async (id: string): Promise<DataSource | null> => {
  try {
    return await apiRequest<DataSource>("GET", `datasources/${id}`);
  } catch (error) {
    console.error("Error fetching data source:", error);
    throw error;
  }
};

export const createDataSource = async (
  dataSourceData: DataSource
): Promise<DataSource> => {
  try {
    const response = await apiRequest<DataSource>(
      "POST",
      "datasources",
      JSON.parse(JSON.stringify(dataSourceData))
    );
    return response;
  } catch (error) {
    console.error("Error creating data source:", error);
    throw error;
  }
};

export const updateDataSource = async (
  id: string,
  dataSourceData: Partial<DataSource>
): Promise<DataSource> => {
  try {
    const response = await apiRequest<DataSource>(
      "PUT",
      `datasources/${id}`,
      JSON.parse(JSON.stringify(dataSourceData))
    );
    return response;
  } catch (error) {
    console.error("Error updating data source:", error);
    throw error;
  }
};

export const deleteDataSource = async (id: string): Promise<void> => {
  try {
    await apiRequest<void>("DELETE", `datasources/${id}`);
  } catch (error) {
    console.error("Error deleting data source:", error);
    throw error;
  }
};
